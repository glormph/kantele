'''
Script to MD5, register, and upload files to Kantele system


Usecases:
    - Instrument auto upload using an API key
        python upload.py --client abc123 --watch_folder /path/to/outbox
    - User big file uploads -  python upload.py --token abc123 --file /path/to/file
      - login, get token for upload, run script
    - User lots of files - python upload.py --token abc123 --watch_folder /path/to/outbox
    - Libfile uploads -  python upload.py --token abc123 --libfile /path/to/file
      - as user big file
      - gets turned into libfile
    - Microscopy uploads (have a bat script for unknowing users) :
      - python upload.py --client abc123 --watch_folder /path/to outbox
      - as instrument only need backup
    - Seq. backup bunch of FASTQ uploads, encrypt (login first for token, specify SENS, batch of files)
      upload.py --token abc123 --watch_folder /path/to/outbox --keyfile .ssh/key 

Views where you get token should be:
    - showing the current uploads, i.e. admin page for file input
    - instrument installation thing
    - upload script install download
    - browser upload, is_libfile, or get token
'''



import sys
import logging
import logging.handlers
import os
import argparse
import json
import hashlib
import requests
import subprocess
import shutil
from base64 import b64decode
from urllib.parse import urljoin
from time import sleep
from multiprocessing import Process, Queue, set_start_method, TimeoutError
from queue import Empty

LEDGERFN = 'ledger.json'

def zipfolder(folder, arcname):
    print('zipping {} to {}'.format(folder, arcname))
    return shutil.make_archive(arcname, 'zip', folder)


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()




def get_new_file_entry(fn, ftype, raw_is_folder):
    if raw_is_folder or os.path.isdir(fn):
        size = sum(os.path.getsize(os.path.join(wpath, subfile))
            for wpath, subdirs, files in os.walk(fn) for subfile in files if subfile)
    else:
        size = os.path.getsize(fn)
    return {'fpath': fn, 'fname': os.path.basename(fn),
            'md5': False, 'ftype_id': ftype,
            'fn_id': False,
            'prod_date': str(os.path.getctime(fn)),
            'size': size,
            'is_dir': raw_is_folder or os.path.isdir(fn),
            'transferred': False}
            #'remote_checking': False, 'remote_ok': False}


def save_ledger(ledger, ledgerfile):
    with open(ledgerfile, 'w') as fp:
        json.dump(ledger, fp)


def register_file(host, url, fn, fn_md5, size, date, client_id, claimed, **postkwargs):
    url = urljoin(host, url)
    postdata = {'fn': fn,
                'client_id': client_id,
                'md5': fn_md5,
                'size': size,
                'date': date,
                'claimed': claimed,
                }
    if postkwargs:
        postdata.update(postkwargs)
    return requests.post(url=url, data=postdata)


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


def instrument_collector(regq, fndoneq, logq, ledger, outbox, zipbox, hostname, filetype, raw_is_folder, md5_stable_fns):
    # FIXME stop watching if this is a token upload
    """Runs as process, periodically checks outbox,
    runs MD5 on newly discovered files,
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
            fndata = get_new_file_entry(fn, filetype, raw_is_folder)
            ct_size = get_fndata_id(fndata)
            if ct_size not in ledger:
                prod_date = fndata['prod_date']
                logger.info('Found new file: {} produced {}'.format(fn, prod_date))
                ledger[ct_size] = fndata
        for produced_fn in ledger.values():
            if not produced_fn['md5']:
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
                    produced_fn['md5'] = md5(produced_fn['fpath'])
                except FileNotFoundError:
                    logger.warning('Could not find file in outbox to check MD5')
                    continue
                else:
                    regq.put(produced_fn)
            if produced_fn['is_dir'] and 'nonzipped_path' not in produced_fn:
                if not os.path.exists(zipbox):
                    os.makedirs(zipbox)
                zipname = os.path.join(zipbox, os.path.basename(produced_fn['fpath']))
                produced_fn['nonzipped_path'] = produced_fn['fpath']
                produced_fn['fpath'] = zipfolder(produced_fn['fpath'], zipname)
        sleep(5)


def proc_log_configure(queue):
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


def register_and_transfer(regq, regdoneq, logqueue, ledger, donebox, single_file_id, client_id, kantelehost, clientname, scp_full, keyfile):
    # FIXME where to do library check? In register process I guess.
    '''This process does the registration and the transfer of files'''
    # Start getting the leftovers from previous run
    fnstate_url = urljoin(kantelehost, 'files/transferstate/')
    trfed_url = urljoin(kantelehost, 'files/transferred/')
    newfns_found = False
    proc_log_configure(logqueue)
    logger = logging.getLogger(f'{clientname}.producer.main')
    while True:
        for fndata in [x for x in ledger.values() if not x['fn_id']]:
            # In case new files are found but registration failed for some 
            # reason, MD5 is on disk (only to ledger after MD5), re-register
            regq.put(fndata)
        while regq.qsize():
            newfns_found = True
            fndata = regq.get()
            ct_size = get_fndata_id(fndata)
            # update ledger in case new MD5 calculated
            ledger[ct_size] = fndata
            try:
                resp = register_file(kantelehost, 'files/register/', fndata['fname'],
                        fndata['md5'], fndata['size'], fndata['prod_date'], 
                        client_id, claimed=False)
            except requests.exceptions.ConnectionError:
                logger.error('Cannot connect to kantele server')
                # no server, try again later
            else:
                if resp.status_code == 200:
                    resp_j = resp.json()
                    logger.info('File {} matches remote file {} with ID '
                            '{}'.format(fndata['fname'], resp_j['remote_name'], resp_j['file_id']))
                    fndata['fn_id'] = resp_j['file_id']
                else:
                    logger.error('Could not register file, error code {}, please check with admin'.format(resp.status_code))
        # Persist state of zipped/MD5/fn_ids to disk
        if newfns_found:
            save_ledger(ledger, LEDGERFN)

        # Now find what to do with all registered files and do it
        scpfns, ledgerchanged = [], False
        if single_file_id and ledger[single_file_id]['fn_id']:
            to_process = [(single_file_id, ledger[single_file_id]['fn_id'], ledger[single_file_id])]
        elif single_file_id:
            to_process = []
        else:
            to_process = [(k, x['fn_id'], x)  for k, x in ledger.items() if x['fn_id']]
        for cts_id, fnid, fndata in to_process:
            try:
                resp = requests.post(fnstate_url, json={'fnid': fnid, 'client_id': client_id})
            except requests.exceptions.ConnectionError:
                logger.error('Cannot connect to kantele server, will retry')
                # try again later
                continue
            if resp.status_code != 500:
                result = resp.json()
            else:
                result = {'error': 'Kantele server error when getting file state, please contact administrator'}
            logger.info('Checking remote state for file {} with ID {}'.format(fndata['fname'], fnid))
            if resp.status_code != 200:
                logger.error('Could not get state for file with ID {}, error message '
                        'was: {}'.format(fnid, result['error']))
            elif result['transferstate'] == 'done':
                logger.info('State for file with ID {} was "done", removing from outbox'.format(fnid))
                # Remove done files from ledger/outbox
                if fndata['is_dir']:
                    # Zipped intermediate files are removed here
                    if os.path.exists(fndata['fpath']):
                        os.remove(fndata['fpath'])
                    file_done = fndata['nonzipped_path']
                else:
                    file_done = fndata['fpath']
                if donebox:
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
                if single_file_id:
                    # Quit loop for single file
                    # FIXME quit higher loop!
                    break
            elif result['transferstate'] == 'transfer':
                scpfns.append((cts_id, fndata))
            else:
                logger.info('State for file {} with ID {} was: {}'.format(fndata['fname'], fnid, result['transferstate']))

            # Now transfer registered files (TODO put in mp Process/Q? ledger?)
            # In MP case you will need to also report start of transfer so
            # it wont queue for SCP multiple times etc? Maybe queued could
            # re-check state on server before doing the SCP

            for cts_id, fndata in scpfns:
                if cts_id not in ledger:
                    logger.warning('Could not find file with ID {} locally'.format(fndata['fn_id']))
                    continue
                if not fndata['transferred']:
                    # local state on produced fns so we dont retransfer
                    # if no MD5 is validated on server yet
                    try:
                        transfer_file(fndata['fpath'], scp_full, keyfile)
                    except subprocess.CalledProcessError:
                        logger.warning('Could not transfer {}'.format(
                            fndata['fpath']))
                    else:
                        fndata['transferred'] = True
                        trf_data = {'fn_id': fndata['fn_id'],
                                # use fpath/basename instead of fname, to get the
                                # zipped file name if needed, instead of the normal fn 
                                'filename': os.path.basename(fndata['fpath']),
                                'client_id': client_id,
                                'ftype_id': fndata['ftype_id'],
                                }
                        resp = requests.post(url=trfed_url, data=trf_data)
                        if resp.status_code == 500:
                            logger.error('Kantele server error when getting file state, please contact administrator')
                        else:
                            result = resp.json()
                            if resp.status_code != 200:
                                logger.error(result['error'])
                                if 'problem' in result and result['problem'] == 'NOT_REGISTERED':
                                    fndata.update({
                                        'md5': False, 'registered': False,
                                        'transferred': False,
                                        'remote_checking': False,
                                        'remote_ok': False})
                            else:
                                logger.info('Registered transfer of file '
                                 '{}'.format(fndata['fpath']))
                        ledgerchanged = True
            if ledgerchanged:
                save_ledger(ledger, LEDGERFN)
        sleep(3)


def main():
    # Set Process method to spawn to not inherit shared objects
    # this is what normally happens on windows/MacOS anyway, but on Unix
    # we get double entries in log from processes due to attaching queue handler
    # in both main process and worker process.
    set_start_method('spawn')

    # backup-only, sensitive data is specified by DB on the host when getting a token!
    parser = argparse.ArgumentParser(description='File uploader')
    parser.add_argument('--watch_folder', dest='outbox', default=False, type=str,
            help='Outbox folder to watch if any')
    parser.add_argument('--file', dest='file', default=False, type=str, help='File to upload')
    parser.add_argument('--config', dest='configfn', default=False, type=str, help='Config file if any')
    parser.add_argument('--library_description', type=str, dest='libdesc', default=False,
            help='In case you want a library file to be uploaded (will be shared for analysis), '
            'provide its description here (in quotes)')
    parser.add_argument('--client', type=str, dest='client_id', default=False,
            help='Client ID for instrument')
    args = parser.parse_args()

    # Load settings if any
    if args.configfn:
        with open(args.configfn) as fp:
            config = json.load(fp)

    mainq = Queue()
    regdoneq = Queue()
    regq = Queue()
    logqueue = Queue()

    try:
        with open(LEDGERFN) as fp:
            ledger = json.load(fp)
    except IOError:
        ledger = {}
    # FIXME no ledger for single file upload?
    # stateless is better there in case of crash or something
    # But say you have a single file big zip, and prefer not to re-zip after an SCP failure,
    # then it is nice with a ledger

    if not args.client_id:
        webtoken = input('Please provide token from web interface: ').strip()
        try:
            token, filetype_id, kantelehost = b64decode(webtoken).decode('utf-8').split('|')
        except ValueError:
            print('Incorrect token')
            sys.exit(1)

    outbox = args.outbox or config.get('outbox')
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
        collect_p = Process(target=instrument_collector, args=(regq, regdoneq, logqueue, ledger, outbox, zipbox, config.get('hostname')))
        processes = [collect_p]
        collect_p.start()
    elif args.file:
        # Single file upload
        donebox = False
        # check if it is in ledger, use that then
        # TODO add question -- should we use ledger
        # FIXME filetype and raw_is_folder should be dynamic
        # maybe raw_is_folder ALWAYS dynamic
        fndata = get_new_file_entry(args.file, config.get('filetype_id'), config.get('raw_is_folder'))
        single_file_id = get_fndata_id(fndata)
        if single_file_id in ledger:
            fndata = ledger[single_file_id]
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
        processes = []
    else:
        print('No input files or outbox to watch was specified, exiting')
        sys.exit(1)
    register_p = Process(target=register_and_transfer, args=(regq, regdoneq, logqueue, ledger, donebox, single_file_id, args.client_id))
    register_p.start()
    logproc = Process(target=log_listener, args=(logqueue,))
    logproc.start()
    processes.extend([logproc, register_p])
    quit = False
    while True:
        for p in processes:
            if not p.is_alive():
                print(f'Crash detected in {p}, exiting')
                quit = True
                break
        if quit:
            break
        mainq.put('heartbeat')
        sleep(2)
    for p in processes:
        p.terminate()
        p.join()


if __name__ == '__main__':
    main()
