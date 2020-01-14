import sys
import logging
import os
import json
import hashlib
import requests
import subprocess
from urllib.parse import urljoin
from time import sleep
from json.decoder import JSONDecodeError
import shutil

LEDGERFN = 'ledger.json'
UPLOAD_FILETYPE_ID = os.environ.get('FILETYPE_ID')
KANTELEHOST = os.environ.get('KANTELEHOST')
RAW_IS_FOLDER = int(os.environ.get('RAW_IS_FOLDER')) == 1
OUTBOX = os.environ.get('OUTBOX')
ZIPBOX = os.environ.get('ZIPBOX')
DONEBOX = os.environ.get('DONEBOX')
CLIENT_ID = os.environ.get('CLIENT_ID')
KEYFILE = os.environ.get('KEYFILE')
SCP_FULL = os.environ.get('SCP_FULL')


def zipfolder(folder, arcname):
    print('zipping {} to {}'.format(folder, arcname))
    return shutil.make_archive(arcname, 'zip', folder)


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def check_transfer_success(host, urlpath, fn_id, ftype_id, client_id, **getkwargs):
    url = urljoin(host, urlpath)
    params = {'fn_id': fn_id, 'client_id': client_id, 'ftype_id': ftype_id}
    if getkwargs:
        params.update(getkwargs)
    return requests.get(url=url, params=params)


def register_transfer(host, fn_id, fpath, ftype_id, client_id):
    url = urljoin(host, 'files/transferred/')
    postdata = {'fn_id': fn_id, 'filename': os.path.basename(fpath),
                'client_id': client_id,
                'ftype_id': ftype_id,
                }
    return requests.post(url=url, data=postdata)


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


def save_ledger(ledger, ledgerfile):
    with open(ledgerfile, 'w') as fp:
        json.dump(ledger, fp)


def transfer_file(fpath, transfer_location, keyfile):
    """Transfer location will be something like login@server:/path/to/storage"""
    logging.info('Transferring {} to {}'.format(fpath, transfer_location))
    remote_path = os.path.join(transfer_location + '/', os.path.basename(fpath))
    if sys.platform.startswith("win"):
        subprocess.check_call(['pscp.exe', '-i', keyfile, fpath, remote_path])
    else:
        subprocess.check_call(['scp', '-i', keyfile, fpath, remote_path])


def collect_outbox(outbox, ledger, ledgerfn):
    if not os.path.exists(outbox):
        os.makedirs(outbox)
    if ZIPBOX is not None and not os.path.exists(ZIPBOX):
        os.makedirs(ZIPBOX)
    logging.info('Checking outbox')
    for fn in [os.path.join(outbox, x) for x in os.listdir(outbox)]:
        prod_date = str(os.path.getctime(fn))
        if fn not in ledger:
            logging.info('Found new file: {} produced {}'.format(fn, prod_date))
            ledger[fn] = {'fpath': fn, 'fname': os.path.basename(fn), 
                'md5': False, 'ftype_id': UPLOAD_FILETYPE_ID,
                'prod_date': str(os.path.getctime(fn)),
                'is_dir': RAW_IS_FOLDER,
                'registered': False, 'transferred': False,
                'remote_checking': False, 'remote_ok': False}
            save_ledger(ledger, ledgerfn)
    for produced_fn in ledger.values():
        if produced_fn['is_dir'] and 'nonzipped_path' not in produced_fn:
            zipname = os.path.join(ZIPBOX, os.path.basename(produced_fn['fpath']))
            produced_fn['nonzipped_path'] = produced_fn['fpath']
            produced_fn['fpath'] = zipfolder(produced_fn['fpath'], zipname)
            save_ledger(ledger, ledgerfn)
        print(produced_fn['fpath'])
        if not produced_fn['md5']:
            try:
                produced_fn['md5'] = md5(produced_fn['fpath'])
            except FileNotFoundError:
                logging.warning('Could not find file in outbox to check MD5')
                continue
            save_ledger(ledger, ledgerfn)


def register_outbox_files(ledger, ledgerfn, kantelehost, url, client_id, claimed=False, **postkwargs):
    logging.info('Checking files to register')
    for fn, produced_fn in ledger.items():
        if not produced_fn['registered']:
            size = os.path.getsize(produced_fn['fpath'])
            reg_response = register_file(kantelehost, url, produced_fn['fname'], 
                produced_fn['md5'], size, produced_fn['prod_date'],
                client_id, claimed, **postkwargs)
            js_resp = reg_response.json()
            if js_resp['state'] == 'registered':
                produced_fn['remote_id'] = js_resp['file_id']
                produced_fn['registered'] = True
                if ('stored' in js_resp and js_resp['stored'] and
                        js_resp['md5'] == produced_fn['md5']):
                    produced_fn['transferred'] = True
            elif js_resp['state'] == 'error':
                logging.warning('Server reported an error: {}'.format(js_resp['msg']))
                if 'md5' in js_resp:
                    logging.warning('Registered and local file MD5 do {} match'
                                    ''.format('' if js_resp['md5'] ==
                                              produced_fn['md5'] else 'NOT'))
                    produced_fn['registered'] = True
                if 'file_id' in js_resp:
                    produced_fn['remote_id'] = js_resp['file_id']
            save_ledger(ledger, ledgerfn)


def transfer_outbox_files(ledger, ledgerfn, transfer_location, keyfile,
        kantelehost, client_id):
    logging.info('Checking transfer of files')
    for produced_fn in ledger.values():
        if produced_fn['registered'] and not produced_fn['transferred']:
            logging.info('Found file not registerered, not transferred: {}'
                         ''.format(produced_fn['fpath']))
            try:
                transfer_file(produced_fn['fpath'], transfer_location, keyfile)
            except subprocess.CalledProcessError:
                logging.warning('Could not transfer {}'.format(
                    produced_fn['fpath']))
            else:
                produced_fn['transferred'] = True
                save_ledger(ledger, ledgerfn)
                register_transferred_files(ledger, ledgerfn, kantelehost,
                                           client_id)


def register_transferred_files(ledger, ledgerfn, kantelehost, client_id):
    logging.info('Register transfer of files if necessary')
    for produced_fn in ledger.values():
        if produced_fn['transferred'] and not produced_fn['remote_checking']:
            response = register_transfer(kantelehost, produced_fn['remote_id'],
                                         produced_fn['fpath'],
                                         produced_fn['ftype_id'], client_id)
                                         
            try:
                js_resp = response.json()
            except JSONDecodeError:
                logging.warning('Server error registering file, will retry later')
                continue
            if js_resp['state'] == 'error':
                logging.warning('File with ID {} not registered yet'
                                ''.format(produced_fn['remote_id']))
                produced_fn.update({'md5': False, 'registered': False,
                                    'transferred': False,
                                    'remote_checking': False,
                                    'remote_ok': False})
            else:
                logging.info('Registered transfer of file '
                             '{}'.format(produced_fn['fpath']))
                produced_fn['remote_checking'] = True
            save_ledger(ledger, ledgerfn)


def check_success_transferred_files(ledger, ledgerfn, kantelehost, url, client_id,
                                    **getkwargs):
    logging.info('Check transfer of files')
    for produced_fn in ledger.values():
        if produced_fn['remote_checking'] and not produced_fn['remote_ok']:
            response = check_transfer_success(kantelehost, url,
                                              produced_fn['remote_id'],
                                              produced_fn['ftype_id'],
                                              client_id, **getkwargs)
            try:
                js_resp = response.json()
            except JSONDecodeError:
                logging.warning('Server error checking success transfer file, '
                             'trying again later')
                continue
            if not js_resp['md5_state']:
                continue
            elif js_resp['md5_state'] == 'error':
                produced_fn['transferred'] = False
                produced_fn['remote_checking'] = False
            elif js_resp['md5_state'] == 'ok':
                produced_fn['remote_ok'] = True
            save_ledger(ledger, ledgerfn)


def check_done(ledger, ledgerfn, kantelehost, client_id, donebox):
    if not os.path.exists(donebox):
        os.makedirs(donebox)
    check_success_transferred_files(ledger, ledgerfn, kantelehost, 'files/md5/',
                                    client_id)
    for file_done in [k for k, x in ledger.items() if x['remote_ok']]:
        if ledger[file_done]['is_dir']:
            if os.path.exists(ledger[file_done]['fpath']):
                os.remove(ledger[file_done]['fpath'])
            file_done = ledger[file_done]['nonzipped_path']
        else:
            file_done = ledger[file_done]['fpath']
        logging.info('Finished with file {}: '
                     '{}'.format(file_done, ledger[file_done]))
        try:
            shutil.move(file_done,
                        os.path.join(donebox, os.path.basename(file_done)))
        except FileNotFoundError:
            continue
        finally:
            del(ledger[file_done])
    save_ledger(ledger, ledgerfn)


def set_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler('filetransfer.log')])


def main():
    set_logger()
    try:
        with open(LEDGERFN) as fp:
            ledger = json.load(fp)
    except IOError:
        ledger = {}
    while True:
        collect_outbox(OUTBOX, ledger, LEDGERFN)
        register_outbox_files(ledger, LEDGERFN, KANTELEHOST, 'files/register/', 
                CLIENT_ID)
        transfer_outbox_files(ledger, LEDGERFN, SCP_FULL, KEYFILE,
                              KANTELEHOST, CLIENT_ID)
        # registers are done after each transfer, this one is to wrap them up
        register_transferred_files(ledger, LEDGERFN, KANTELEHOST, CLIENT_ID)
        check_done(ledger, LEDGERFN, KANTELEHOST, CLIENT_ID, DONEBOX)
        sleep(10)


if __name__ == '__main__':
    main()
