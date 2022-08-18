'''
Script to MD5, register, and upload files to Kantele system

# to test
- transferring while getting new tokens
- make sure old tokens are bust
- transfer by hand
- browser fasta transfer

Usecases:
    - Instrument auto upload using an API key (config file from Kantele)
        python upload.py --config transfer_config.json

    - User file uploads (non-fasta)
      - An upload token will be asked for and can be requested from Kantele web interface
        python upload.py --file /path/to/file

    - Libfile uploads (fasta etc), as above but with a library description
        python upload.py --token abc123 --file /path/to/file --library-description "this is a file"

    - External instrument uploads
      - python upload.py --client abc123 --outbox /path/to outbox

    - Sensitive data uploads, e.g. backup bunch of FASTQ uploads, encrypt
      - specify SENS when getting token
      upload.py --token abc123 --outbox /path/to/outbox 
'''

# TODO make check_in procedure a main loop thing, restart processes when they need
# to make a change in config (new token, pub key, new folder name, etc)

# - TODO generate and upload SSH pub key

# FIXME look over the args to make sure no crap is in it

import sys
import logging
import logging.handlers
import os
import argparse
import getpass
import json
import hashlib
import requests
import subprocess
import shutil
from base64 import b64decode
from urllib.parse import urljoin
from time import sleep, time
from multiprocessing import Process, Queue, set_start_method, TimeoutError
from queue import Empty

LEDGERFN = 'ledger.json'
HEARTBEAT_SECONDS = 5 * 60
 
def zipfolder(folder, arcname):
    print('zipping {} to {}'.format(folder, arcname))
    return shutil.make_archive(arcname, 'zip', folder)


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_new_file_entry(fn, raw_is_folder):
    if raw_is_folder or os.path.isdir(fn):
        size = sum(os.path.getsize(os.path.join(wpath, subfile))
            for wpath, subdirs, files in os.walk(fn) for subfile in files if subfile)
    else:
        size = os.path.getsize(fn)
    return {'fpath': fn, 'fname': os.path.basename(fn),
            'md5': False,
            'fn_id': False,
            'prod_date': str(os.path.getctime(fn)),
            'size': size,
            'is_dir': raw_is_folder or os.path.isdir(fn),
            'transferred': False}
            #'remote_checking': False, 'remote_ok': False}


def get_csrf(cookies, referer_host):
    return {'X-CSRFToken': cookies['csrftoken'], 'Referer': referer_host}


def check_in_instrument(config, configfn, logger):
    '''Check in instrument with backend to get/renew/validate token, and provide
    a client heartbeat to backend.
    This function has side-effects in that it mutates config dict, which is why
    it is only called once pre-setup and further only in the register-thread, as
    no other thread needs this config (for updates)
    '''
    clid = config.get('client_id', False)
    kantelehost = config['host']
    loginurl = urljoin(kantelehost, 'login/')
    token_state = False
    session = requests.session()
    if not config.get('token', False):
        print('''
         _               _       _      
        | | ____ _ _ __ | |_ ___| | ___ 
        | |/ / _` | '  \\| __/ _ \ |/ _ \\
        |   < (_| | | | | ||  __/ |  __/
        |_|\_\__,_|_| |_|\__\___|_|\___|

    ******************************************
    Please login to kantele to begin instrument upload monitoring.

        ''')
        passwordfail = False
        for _i in range(3):
            if _i:
                print('Wrong username/password combination, try again')
                if _i == 2:
                    print('Last try')
                    passwordfail = True
            username = input('Kantele username: ')
            password = getpass.getpass('Kantele password: ')
            init_resp = session.get(loginurl)
            loginresp = session.post(loginurl,
                    data={'username': username, 'password': password},
                    headers=get_csrf(session.cookies, kantelehost))
            tokenresp = session.post(urljoin(kantelehost, 'files/token/'),
                    headers=get_csrf(session.cookies, kantelehost),
                    json={'producer_id': clid, 'ftype_id': config['filetype_id']})
            if tokenresp.status_code != 403:
                break
            if passwordfail:
                print('Could not log you in')
                sys.exit(1)

        result = tokenresp.json()
        logger.info(f'Got a new token from server, which will expire on {result["expires"]}')
        token_state = 'new'
        config['token'] = result['token']
    elif clid:
        # Validate/renew existing token
        loginresp = session.get(loginurl)
        valresp = session.post(urljoin(kantelehost, 'files/instruments/check/'),
                headers=get_csrf(loginresp.cookies, kantelehost),
                json={'token': config['token'], 'client_id': clid})
        if valresp.status_code == 403:
            logger.error('Token expired or invalid, will try to fetch new token')
            del(config['token'])
            # Call itself to get new fresh token
            token_state = check_in_instrument(config, configfn, logger)
            token_state = 'ok' # already new/saved in nested function call
        elif valresp.status_code == 500:
            return 'Could not check in instrument due to server error, talk to admin'
        elif valresp.status_code != 200:
            return 'Could not check in instrument, server replied {resp["error"]}'
        else:
            validated = valresp.json()
            logger.info(f'Got a new token from server, which will expire on {validated["expires"]}')
            if validated['newtoken']:
                token_state = 'new'
                config['token'] = validated['newtoken']
    if token_state == 'new':
        with open(configfn, 'w') as fp:
            json.dump(config, fp)
    return False


def save_ledger(ledger, ledgerfile):
    with open(ledgerfile, 'w') as fp:
        json.dump(ledger, fp)


def register_file(host, url, fn, fn_md5, size, date, cookies, token, claimed, **postkwargs):
    url = urljoin(host, url)
    postdata = {'fn': fn,
                'token': token,
                'md5': fn_md5,
                'size': size,
                'date': date,
                'claimed': claimed,
                }
    if postkwargs:
        postdata.update(postkwargs)
    return requests.post(url=url, cookies=cookies, headers=get_csrf(cookies, host), json=postdata)


def transfer_file(fpath, transfer_location, keyfile):
    """Transfer location will be something like login@server:/path/to/storage"""
    logging.info('Transferring {} to {}'.format(fpath, transfer_location))
    remote_path = os.path.join(transfer_location + '/', os.path.basename(fpath))
    if sys.platform.startswith("win"):
        subprocess.check_call(['pscp.exe', '-i', keyfile, fpath, remote_path])
    else:
        subprocess.check_call(['scp', '-i', keyfile, fpath, remote_path])


def get_fndata_id(fndata):
    return '{}__{}'.format(fndata['prod_date'], fndata['size'])


def instrument_collector(regq, fndoneq, logq, ledger, outbox, zipbox, hostname, raw_is_folder, md5_stable_fns):
    """Runs as process, periodically checks outbox,
    runs MD5 and if needed zip (folder) on newly discovered files,
    process own ledger is kept for new file adding,
    and a queue is used to get updates that remove files.
    """
    proc_log_configure(logq)
    logger = logging.getLogger(f'{hostname}.producer.inboxcollect')
    while True:
        while fndoneq.qsize():
            # These files will have been removed from outbox
            cts_id = fndoneq.get()
            if cts_id in ledger:
                del(ledger[cts_id])
        logger.info(f'Checking for new files in {outbox}')
        for fn in [os.path.join(outbox, x) for x in os.listdir(outbox)]:
            # create somewhat unique identifier to filter against existing entries
            fndata = get_new_file_entry(fn, raw_is_folder)
            ct_size = get_fndata_id(fndata)
            if ct_size not in ledger:
                prod_date = fndata['prod_date']
                logger.info('Found new file: {} produced {}'.format(fn, prod_date))
                ledger[ct_size] = fndata
        for produced_fn in ledger.values():
            newfn = False
            if not produced_fn['md5']:
                newfn = True
                if produced_fn['is_dir']:
                    try:
                        stable_fn = [x for x in md5_stable_fns 
                                if os.path.exists(os.path.join(produced_fn['fpath'], x))][0]
                    except IndexError:
                        logger.warning('This file is a directory, but we could not find a designated stable file inside it')
                        continue
                    md5path = os.path.join(produced_fn['fpath'], stable_fn)
                else:
                    md5path = produced_fn['fpath']
                try:
                    produced_fn['md5'] = md5(md5path)
                except FileNotFoundError:
                    logger.warning('Could not find file in outbox to check MD5')
                    continue
            if produced_fn['is_dir'] and 'nonzipped_path' not in produced_fn:
                newfn = True
                if not os.path.exists(zipbox):
                    os.makedirs(zipbox)
                zipname = os.path.join(zipbox, os.path.basename(produced_fn['fpath']))
                produced_fn['nonzipped_path'] = produced_fn['fpath']
                produced_fn['fpath'] = zipfolder(produced_fn['fpath'], zipname)
            if newfn:
                regq.put(produced_fn)
        sleep(5)


def proc_log_configure(queue):
    '''Configure logger for a specific process of the multiprocessing setup'''
    handler = logging.handlers.QueueHandler(queue)
    logroot = logging.getLogger()
    logroot.removeHandler(handler)
    logroot.addHandler(handler)
    # do not filter here
    logroot.setLevel(logging.INFO)


def log_listener(log_q):
    """A logger target function for the logging Process"""
    logroot = logging.getLogger()
    sh = logging.StreamHandler()
    fh = logging.handlers.TimedRotatingFileHandler('filetransfer.log', when='midnight')
    f = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    sh.setFormatter(f)
    fh.setFormatter(f)
    logroot.addHandler(sh)
    logroot.addHandler(fh)
    while True:
        if log_q.qsize():
            logrec = log_q.get()
            if logrec == False:
                break
            logger = logging.getLogger(logrec.name)
            logger.handle(logrec)


def register_and_transfer(regq, regdoneq, logqueue, ledger, config, configfn, donebox, 
        single_file_id, kantelehost, clientname, scp_full, keyfile, library_desc, user_desc):
    '''This process does the registration and the transfer of files'''
    # Start getting the leftovers from previous run
    fnstate_url = urljoin(kantelehost, 'files/transferstate/')
    trfed_url = urljoin(kantelehost, 'files/transferred/')
    newfns_found = False
    proc_log_configure(logqueue)
    logger = logging.getLogger(f'{clientname}.producer.worker')
    heartbeat_t = time()
    while True:
        loginresp = requests.get(urljoin(kantelehost, 'login/'))
        cookies = loginresp.cookies
        for fndata in [x for x in ledger.values() if not x['fn_id']]:
            # In case new files are found but registration failed for some 
            # reason, MD5 is on disk (only to ledger after MD5), re-register
            regq.put(fndata)
        regqsize = regq.qsize()
        if regqsize:
            logger.info(f'Registering {regqsize} new file(s)')
        for _i in range(regq.qsize()):
            # DO NOT USE: while regq.qsize():
            # that leads to potential eternal loop when flooded every five seconds
            newfns_found = True
            fndata = regq.get()
            ct_size = get_fndata_id(fndata)
            # update ledger in case new MD5 calculated
            ledger[ct_size] = fndata
            try:
                resp = register_file(kantelehost, 'files/register/', fndata['fname'],
                        fndata['md5'], fndata['size'], fndata['prod_date'], 
                        cookies, config['token'], claimed=False)
            except requests.exceptions.ConnectionError:
                logger.error('Cannot connect to kantele server trying to register '
                        f'file {fndata["fname"]}, will try later')
            else:
                if resp.status_code == 200:
                    resp_j = resp.json()
                    logger.info(f'File {fndata["fname"]} matches remote file '
                            f'{resp_j["remote_name"]} with ID {resp_j["file_id"]}')
                    fndata['fn_id'] = resp_j['file_id']
                elif resp.status_code == 403:
                    resp_j = resp.json()
                    logger.error(f'Permission denied registering file, server replied '
                            f' with {resp_j["error"]}')
                elif resp.status_code != 500:
                    resp_j = resp.json()
                    logger.error(f'Problem registering file, server replied with {resp_j["error"]}')
                else:
                    logger.error('Could not register file, error code {}, likely problem is on server, please check with admin'.format(resp.status_code))
                if resp.status_code != 200:
                    # Exit when permission denied, need a new password from user
                    # exit also at server/client errors
                    sys.exit(resp.status_code)
        # Persist state of zipped/MD5/fn_ids to disk
        if newfns_found:
            save_ledger(ledger, LEDGERFN)

        # Now find what to do with all registered files and do it
        scpfns, ledgerchanged = [], False
        if single_file_id and single_file_id in ledger and ledger[single_file_id]['fn_id']:
            to_process = [(single_file_id, ledger[single_file_id]['fn_id'], ledger[single_file_id])]
        elif single_file_id:
            to_process = []
        else:
            to_process = [(k, x['fn_id'], x)  for k, x in ledger.items() if x['fn_id']]
        for cts_id, fnid, fndata in to_process:
            logger.info('Checking remote state for file {} with ID {}'.format(fndata['fname'], fnid))
            try:
                resp = requests.post(fnstate_url, cookies=cookies,
                        headers=get_csrf(cookies, kantelehost),
                        json={'fnid': fnid, 'token': config['token']})
            except requests.exceptions.ConnectionError:
                logger.error('Cannot connect to kantele server to request state '
                f'for file {fndata["fname"]}, will retry')
                continue
            if resp.status_code != 500:
                result = resp.json()
            else:
                result = {'error': 'Kantele server error when getting file state, please contact administrator'}
            if resp.status_code != 200:
                logger.error(f'Could not get state for file with ID {fnid}, error '
                        f'message was: {result["error"]}')
                # Exit when permission denied, need a new password from user
                # exit also at server/client errors
                sys.exit(resp.status_code)
            elif result['transferstate'] == 'done':
                logger.info(f'State for file with ID {fnid} was "done"')
                # Remove done files from ledger/outbox
                if fndata['is_dir']:
                    # Zipped intermediate files are removed here
                    if os.path.exists(fndata['fpath']):
                        os.remove(fndata['fpath'])
                    file_done = fndata['nonzipped_path']
                else:
                    file_done = fndata['fpath']
                if donebox:
                    logger.info(f'Removing file {fndata["fname"]} from outbox')
                    donepath = os.path.join(donebox, fndata['fname'])
                    try:
                        shutil.move(file_done, donepath)
                    except FileNotFoundError:
                        logger.warning(f'Could not move {file_done} from outbox to {donepath}')
                        raise
                    finally:
                        regdoneq.put(cts_id)
                del(ledger[cts_id])
                ledgerchanged = True
            elif result['transferstate'] == 'transfer':
                scpfns.append((cts_id, fndata))
            else:
                logger.info('State for file {} with ID {} was: {}'.format(fndata['fname'], fnid, result['transferstate']))
        if single_file_id and not len(ledger.keys()):
            # Quit loop for single file
            break

        # Now transfer registered files
        for cts_id, fndata in scpfns:
            if time() - heartbeat_t > HEARTBEAT_SECONDS:
                checkerr = check_in_instrument(config, configfn, logger)
                if checkerr:
                    logger.error(checkerr)
                    sys.exit(1)
                heartbeat_t = time()
            if cts_id not in ledger:
                logger.warning(f'Could not find file with ID {fndata["fn_id"]} locally')
                continue
            try:
                transfer_file(fndata['fpath'], scp_full, keyfile)
            except subprocess.CalledProcessError:
                logger.warning('Could not transfer {}'.format(
                    fndata['fpath']))
            else:
                trf_data = {'fn_id': fndata['fn_id'],
                        # use fpath/basename instead of fname, to get the
                        # zipped file name if needed, instead of the normal fn
                        'filename': os.path.basename(fndata['fpath']),
                        'token': config['token'],
                        'libdesc': library_desc,
                        'userdesc': user_desc,
                        }
                resp = requests.post(url=trfed_url, cookies=cookies,
                        headers=get_csrf(cookies, kantelehost), json=trf_data)
                if resp.status_code == 500:
                    result = {'error': 'Kantele server error when getting file '
                        'state, please contact administrator'}
                else:
                    result = resp.json()
                if resp.status_code != 200:
                    logger.error(result['error'])
                    if 'problem' in result and result['problem'] == 'NOT_REGISTERED':
                        fndata.update({
                            'md5': False,
                            'remote_checking': False,
                            'remote_ok': False})
                    else:
                        sys.exit(1)
                else:
                    logger.info(f'Registered transfer of file {fndata["fpath"]}')
                ledgerchanged = True
        if ledgerchanged:
            save_ledger(ledger, LEDGERFN)
        if time() - heartbeat_t > HEARTBEAT_SECONDS:
            checkerr = check_in_instrument(config, configfn, logger)
            if checkerr:
                logger.error(checkerr)
                sys.exit(1)
            heartbeat_t = time()
        sleep(3)


def main():
    # Set Process method to spawn to not inherit shared objects
    # this is what normally happens on windows/MacOS anyway, but on Unix
    # we get double entries in log from processes due to attaching queue handler
    # in both main process and worker process.
    set_start_method('spawn')

    # backup-only, sensitive data is specified by DB on the host when getting a token!
    parser = argparse.ArgumentParser(description='File uploader')
    parser.add_argument('--watch-folder', dest='outbox', default=False, type=str,
            help='Outbox folder to watch if any')
    parser.add_argument('--ledger', dest='ledger', default=False, type=str,
            help='Ledger file to use, or to force ledgerless single-file transfer '
            'to use in case of e.g. re-zipping etc.')
    parser.add_argument('--file', dest='file', default=False, type=str, help='File to upload')
    parser.add_argument('--config', dest='configfn', default=False, type=str, help='Config file if any')
    parser.add_argument('--key', dest='key', default=False, type=str, help='SSH key file for transfer')
    parser.add_argument('--scp-dest', dest='scp_dest', default=False, type=str, help='Full SCP destination path like user@server:/path/')
    parser.add_argument('--library-description', type=str, dest='libdesc', default=False,
            help='In case you want a library file to be uploaded (will be shared for analysis), '
            'provide its description here (in quotes)')
    parser.add_argument('--userfile-description', type=str, dest='userdesc', default=False,
            help='For users to describe their file to be uploaded, '
            'provide its description here (in quotes)')
    args = parser.parse_args()

    regdoneq = Queue()
    regq = Queue()
    logqueue = Queue()

    # Load settings if any
    if args.configfn:
        with open(args.configfn) as fp:
            config = json.load(fp)
    else:
        if not args.key or not args.scp_dest:
            print('Must pass all of --key, --scp-dest on command line or use a JSON config file')
            sys.exit(1)
        config = {'key': args.key, 'scp_full': args.scp_dest}

    proc_log_configure(logqueue)
    logger = logging.getLogger(f'{config.get("hostname", "")}.producer.main')

    if not config.get('client_id', False):
        # Parse token gotten from web UI 
        webtoken = input('Please provide token from web interface: ').strip()
        try:
            token, kantelehost = b64decode(webtoken).decode('utf-8').split('|')
        except ValueError:
            print('Incorrect token')
            sys.exit(1)

        config.update({'host': kantelehost, 'token': token})
    elif args.configfn:
        checkerr = check_in_instrument(config, args.configfn, logger)
        if checkerr:
            # No logger process running yet
            print(checkerr)
            sys.exit(1)
    else:
        print('Client ID specified but no JSON config file passed to --config, exiting')
        sys.exit(1)

    # either a config outbox (instruments) or arg (users)
    outbox = args.outbox or config.get('outbox', False)

    if outbox or args.ledger:
        # ledger for outboxes with multiple files to keep track in case 
        # transfer process is stopped, or when enforced using with single file
        try:
            with open(LEDGERFN) as fp:
                ledger = json.load(fp)
        except IOError:
            ledger = {}
    else:
        ledger = {}

    if outbox:
        donebox = config.get('donebox') or os.path.join(outbox, os.path.pardir, 'donebox')
        zipbox = config.get('zipbox') or os.path.join(outbox, os.path.pardir, 'zipbox')
        single_file_id = False
        # for instruments, setup collection/MD5 process
        # otherwise we use a single shot MD5er
        if not os.path.exists(outbox):
            os.makedirs(outbox)
        if not os.path.exists(donebox):
            os.makedirs(donebox)
        # watch outbox for incoming files
        collect_p = Process(target=instrument_collector, args=(regq, regdoneq, logqueue, ledger, outbox, zipbox, config.get('hostname'), config.get('raw_is_folder'), config.get('md5_stable_fns')))
        processes = [collect_p]
        collect_p.start()
    elif args.file:
        # Single file upload by user with token from web GUI
        donebox = False
        # FIXME filetype and raw_is_folder should be dynamic, in token
        # maybe raw_is_folder ALWAYS dynamic
        print('New file found, calculating checksum')
        fndata = get_new_file_entry(args.file, config.get('raw_is_folder', False))
        single_file_id = get_fndata_id(fndata)
        if single_file_id in ledger:
            fndata = ledger[single_file_id]
        # TODO cannot zip yet, there is no "zipbox", maybe make it workdir
        # FIXME align this with collector process
        if fndata['is_dir'] and 'nonzipped_path' not in fndata:
            zipname = os.path.join(zipbox, os.path.basename(fndata['fpath']))
            fndata['nonzipped_path'] = fndata['fpath']
            fndata['fpath'] = zipfolder(fndata['fpath'], zipname)
        if not fndata['md5']:
            try:
                fndata['md5'] = md5(fndata['fpath'])
            except FileNotFoundError:
                logger.warning('Could not find file specified to check MD5')
            else:
                regq.put(fndata)
        print('Finished checksum of file, will try to upload')
        processes = []
    else:
        print('No input files or outbox to watch was specified, exiting')
        sys.exit(1)
    register_p = Process(target=register_and_transfer, args=(regq, regdoneq, logqueue, ledger, config, args.configfn,
        donebox, single_file_id, config.get('host'), config.get('hostname'),
        config.get('scp_full'), config.get('key'), args.libdesc, args.userdesc))
    register_p.start()
    logproc = Process(target=log_listener, args=(logqueue,))
    logproc.start()
    processes.extend([logproc, register_p])
    quit = False
    while True:
        for p in processes:
            if not p.is_alive():
                if p.exitcode:
                    # not 0, including negative ints for terminated by signal
                    print(f'Crash detected in {p}, exiting')
                else:
                    print('Finished transfers')
                quit = True
                break
        if quit:
            break
        sleep(2)
    for p in processes:
        p.terminate()
        p.join()


if __name__ == '__main__':
    main()
