import sys
import os
import json
import hashlib
import requests
from urllib.parse import urljoin
from time import sleep
from json.decoder import JSONDecodeError

import shutil


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def register_transfer(host, fn_id, fpath, client_id):
    url = urljoin(host, 'files/transferred/')
    postdata = {'fn_id': fn_id, 'filename': os.path.basename(fpath),
                'client_id': client_id,
                'ftype': 'raw',
                }
    return requests.post(url=url, data=postdata)


def register_file(host, fn, fn_md5, size, date, client_id):
    url = urljoin(host, 'files/register/')
    postdata = {'fn': fn,
                'client_id': client_id,
                'md5': fn_md5,
                'size': size,
                'date': date,
                }
    return requests.post(url=url, data=postdata)


def save_ledger(ledger, ledgerfile):
    with open(ledgerfile, 'w') as fp:
        json.dump(ledger, fp)


def transfer_file(fpath, transfer_location):
    print('Transferring {} to {}'.format(fpath, transfer_location))
    remote_path = os.path.join(transfer_location, os.path.basename(fpath))
    shutil.copy(fpath, remote_path)
    # FIXME implement


def collect_outbox(outbox, ledger, ledgerfn):
    for fn in [os.path.join(outbox, x) for x in os.listdir(outbox)]:
        prod_date = str(os.path.getctime(fn))
        if prod_date not in ledger:
            print('Found new file: {} produced {}'.format(fn, prod_date))
            ledger[prod_date] = {'fpath': fn, 'md5': False,
                                 'registered': False, 'transferred': False,
                                 'remote_ok': False}
            save_ledger(ledger, ledgerfn)
    for produced_fn in ledger.values():
        if not produced_fn['md5']:
            produced_fn['md5'] = md5(produced_fn['fpath'])
            save_ledger(ledger, ledgerfn)


def register_outbox_files(ledger, ledgerfn, kantelehost, client_id):
    print('Registering files')
    for prod_date, produced_fn in ledger.items():
        if not produced_fn['registered']:
            fn = os.path.basename(produced_fn['fpath'])
            size = os.path.getsize(produced_fn['fpath'])
            reg_response = register_file(kantelehost, fn, produced_fn['md5'],
                                         size, prod_date, client_id)
            js_resp = reg_response.json()
            if js_resp['state'] == 'registered':
                produced_fn['remote_id'] = js_resp['file_id']
                produced_fn['registered'] = True
            elif js_resp['state'] == 'error':
                print('Server reported an error', js_resp['msg'])
                if 'md5' in js_resp:
                    print('Registered and local file MD5 do {} match'.format(
                        '' if js_resp['md5'] == produced_fn['md5'] else 'NOT'))
                    produced_fn['registered'] = True
                    produced_fn['remote_id'] = js_resp['file_id']
                if js_resp['stored'] and js_resp['md5'] == produced_fn['md5']:
                    produced_fn['transferred'] = True
            save_ledger(ledger, ledgerfn)


def transfer_outbox_files(ledger, ledgerfn, transfer_location):
    print('Transferring files')
    for produced_fn in ledger.values():
        if produced_fn['registered'] and not produced_fn['transferred']:
            try:
                transfer_file(produced_fn['fpath'], transfer_location)
            except RuntimeError:
                pass
            else:
                produced_fn['transferred'] = True
                save_ledger(ledger, ledgerfn)


def register_transferred_files(ledger, ledgerfn, kantelehost, client_id):
    print('Registering files for transfer')
    for produced_fn in ledger.values():
        if produced_fn['transferred'] and not produced_fn['remote_ok']:
            response = register_transfer(kantelehost, produced_fn['remote_id'],
                                         produced_fn['fpath'], client_id)
            try:
                js_resp = response.json()
            except JSONDecodeError:
                print('Server error registering file, trying again later')
                continue
            if not js_resp['md5_state']:
                continue
            elif js_resp['md5_state'] == 'error':
                produced_fn['transferred'] = False
            elif js_resp['md5_state'] == 'ok':
                produced_fn['remote_ok'] = True
            save_ledger(ledger, ledgerfn)


def main():
    outbox = sys.argv[1]
    donebox = sys.argv[2]
    ledgerfn = sys.argv[3]
    kantelehost = sys.argv[4]  # http://host.com/kantele
    client_id = sys.argv[5]
    transfer_location = sys.argv[6]  # SCP login@storageserver.com:/home/store
    try:
        with open(ledgerfn) as fp:
            ledger = json.load(fp)
    except IOError:
        ledger = {}
    while True:
        collect_outbox(outbox, ledger, ledgerfn)
        register_outbox_files(ledger, ledgerfn, kantelehost, client_id)
        transfer_outbox_files(ledger, ledgerfn, transfer_location)
        register_transferred_files(ledger, ledgerfn, kantelehost, client_id)
        for file_done_ts in [k for k, x in ledger.items() if x['remote_ok']]:
            file_done = ledger[file_done_ts]['fpath']
            print('Finished with file {}: '
                  '{}'.format(file_done_ts, ledger[file_done_ts]))
            shutil.move(file_done,
                        os.path.join(donebox, os.path.basename(file_done)))
            del(ledger[file_done_ts])
        save_ledger(ledger, ledgerfn)
        sleep(10)


if __name__ == '__main__':
    main()
