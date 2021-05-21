import sys
import logging
import logging.handlers
import os
import json
import hashlib
import requests
import subprocess
import shutil
from urllib.parse import urljoin
from time import sleep
from multiprocessing import Process, Queue, set_start_method, TimeoutError
from signal import SIGKILL
from queue import Empty

LEDGERFN = 'ledger.json'
UPLOAD_FILETYPE_ID = os.environ.get('FILETYPE_ID')
KANTELEHOST = os.environ.get('KANTELEHOST')
RAW_IS_FOLDER = int(os.environ.get('RAW_IS_FOLDER')) == 1
OUTBOX = os.environ.get('OUTBOX', False)
ZIPBOX = os.environ.get('ZIPBOX')
DONEBOX = os.environ.get('DONEBOX')
CLIENT_ID = os.environ.get('CLIENT_ID')
KEYFILE = os.environ.get('KEYFILE')
SCP_FULL = os.environ.get('SCP_FULL')
HOSTNAME = os.environ.get('HOSTNAME')


def zipfolder(folder, arcname):
    print('zipping {} to {}'.format(folder, arcname))
    return shutil.make_archive(arcname, 'zip', folder)


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_new_file_entry(fn):
    return {'fpath': fn, 'fname': os.path.basename(fn),
            'md5': False, 'ftype_id': UPLOAD_FILETYPE_ID,
            'fn_id': False,
            'prod_date': str(os.path.getctime(fn)),
            'size': os.path.getsize(fn),
            'is_dir': RAW_IS_FOLDER,
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


def instrument_collector(regq, fndoneq, logq, ledger):
    """Runs as process, periodically checks outbox,
    runs MD5 on newly discovered files,
    process own ledger is kept for new file adding,
    and a queue is used to get updates that remove files.
    """
    proc_log_configure(logq)
    logger = logging.getLogger(f'{HOSTNAME}.producer.inboxcollect')
    while True:
        logger.info('Checking new file inbox')
        while fndoneq.qsize():
            # These files will have been removed from outbox
            cts_id = fndoneq.get()
            if cts_id in ledger:
                del(ledger[cts_id])
        for fn in [os.path.join(OUTBOX, x) for x in os.listdir(OUTBOX)]:
            # create somewhat unique identifier to filter against existing entries
            fndata = get_new_file_entry(fn)
            ct_size = get_fndata_id(fndata)
            if ct_size not in ledger:
                prod_date = fndata['prod_date']
                logger.info('Found new file: {} produced {}'.format(fn, prod_date))
                ledger[ct_size] = fndata
        for produced_fn in ledger.values():
            if produced_fn['is_dir'] and 'nonzipped_path' not in produced_fn:
                zipname = os.path.join(ZIPBOX, os.path.basename(produced_fn['fpath']))
                produced_fn['nonzipped_path'] = produced_fn['fpath']
                produced_fn['fpath'] = zipfolder(produced_fn['fpath'], zipname)
            if not produced_fn['md5']:
                try:
                    produced_fn['md5'] = md5(produced_fn['fpath'])
                except FileNotFoundError:
                    logger.warning('Could not find file in outbox to check MD5')
                    continue
                else:
                    regq.put(produced_fn)
        sleep(2)


def worker_watcher(mainq, pids):
    """Future: use something like this in case you have more than one process and
    a main, this kills all processes when a single non-alive is found"""
    quit = False
    while True:
        try:
            mainq.get(timeout=5)
        except (TimeoutError, Empty, ValueError):
            print('Main loop crashed, killing all processes')
            [os.kill(pid, SIGKILL) for pid in pids]
            break

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


def register_and_transfer(regq, regdoneq, logqueue, ledger):
    '''This process does the registration and the transfer of files'''
    # Start getting the leftovers from previous run
    fnstate_url = urljoin(KANTELEHOST, 'files/transferstate/')
    trfed_url = urljoin(KANTELEHOST, 'files/transferred/')
    newfns_found = False
    proc_log_configure(logqueue)
    logger = logging.getLogger(f'{HOSTNAME}.producer.main')
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
                resp = register_file(KANTELEHOST, 'files/register/', fndata['fname'],
                        fndata['md5'], fndata['size'], fndata['prod_date'], 
                        CLIENT_ID, claimed=False)
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
        # Persist state of MD5/fn_ids to disk
        if newfns_found:
            save_ledger(ledger, LEDGERFN)

        # Now find what to do with all registered files and do it
        scpfns, ledgerchanged = [], False
        for cts_id, fnid, fndata in [(k, x['fn_id'], x)  for k, x in ledger.items() if x['fn_id']]:
            try:
                resp = requests.post(fnstate_url, json={'fnid': fnid, 'client_id': CLIENT_ID})
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
                donepath = os.path.join(DONEBOX, fndata['fname'])
                try:
                    shutil.move(file_done, donepath)
                except FileNotFoundError:
                    logger.warning(f'Could not move {file_done} from outbox to {donepath}')
                    raise
                finally:
                    del(ledger[cts_id])
                    regdoneq.put(cts_id)
                ledgerchanged = True
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
                        transfer_file(fndata['fpath'], SCP_FULL, KEYFILE)
                    except subprocess.CalledProcessError:
                        logger.warning('Could not transfer {}'.format(
                            fndata['fpath']))
                    else:
                        fndata['transferred'] = True
                        trf_data = {'fn_id': fndata['fn_id'],
                                'filename': fndata['fname'],
                                'client_id': CLIENT_ID,
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

    mainq = Queue()
    regdoneq = Queue()
    regq = Queue()
    logqueue = Queue()
    logproc = Process(target=log_listener, args=(logqueue,))
    logproc.start()
    try:
        with open(LEDGERFN) as fp:
            ledger = json.load(fp)
    except IOError:
        ledger = {}
    # FIXME no ledger for upload_libfile please, stateless is better there
    # make sure this is passed to register_p i.e ledger = False
    register_p = Process(target=register_and_transfer, args=(regq, regdoneq, logqueue, ledger))
    register_p.start()
    processes = [logproc, register_p]
    # FIXME this is a bit clunky, outbox parametrization could be done on cmd line
    # what if you hav it env specified but then want to upload a libfile?
    if OUTBOX:
        # for instruments, setup collection/MD5 process
        # otherwise we use a single shot MD5er
        if not os.path.exists(OUTBOX):
            os.makedirs(OUTBOX)
        if not os.path.exists(DONEBOX):
            os.makedirs(DONEBOX)
        if ZIPBOX is not None and not os.path.exists(ZIPBOX):
            os.makedirs(ZIPBOX)
        collect_p = Process(target=instrument_collector, args=(regq, regdoneq, logqueue, ledger))
        processes.append(collect_p)
        collect_p.start()
    else:
        # FIXME where to do library check? In register process I guess.
        # Single file upload
        fnpath = sys.argv[1]
        description = sys.argv[2]
        fndata = get_new_file_entry(fnpath)
        if produced_fn['is_dir'] and 'nonzipped_path' not in produced_fn:
            zipname = os.path.join(ZIPBOX, os.path.basename(produced_fn['fpath']))
            produced_fn['nonzipped_path'] = produced_fn['fpath']
            produced_fn['fpath'] = zipfolder(produced_fn['fpath'], zipname)
            if not produced_fn['md5']:
                try:
                    produced_fn['md5'] = md5(produced_fn['fpath'])
                except FileNotFoundError:
                    logger.warning('Could not find file specified to check MD5')
                else:
                    regq.put(produced_fn)
    # Not sure if necessary, spawn method seems to kill processes when main goes down
    # at least on linux, test on windows
    watch_p = Process(target=worker_watcher, args=(mainq, [x.pid for x in processes]))
    watch_p.start()
    quit = False
    while True:
        for p in processes + [watch_p]:
            if not p.is_alive():
                print(f'Crash detected in {p}, exiting')
                quit = True
                break
        if quit:
            break
        mainq.put('heartbeat')
        sleep(2)
    for p in processes + [watch_p]:
        p.terminate()
    # Join the spawned processes before exit, possibly not needed?
    logproc.join()
    collect_p.join()
    register_p.join()
    watch_p.join()


if __name__ == '__main__':
    main()
