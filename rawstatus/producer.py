import sys
import os
import json
import hashlib
import requests
from urllib.parse import urljoin


def md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def register_transfer(host, fn_id, client_id):
    url = urljoin(host, 'files/transferred')
    postdata = {'fn_id': fn_id,
                'client_id': client_id,
                }
    requests.post(url=url, data=postdata)


def register_file(host, fn, fn_md5, size, date, client_id):
    url = urljoin(host, 'files/register')
    postdata = {'fn': fn,
                'client_id': client_id,
                'md5': fn_md5,
                'size': size,
                'date': date,
                }
    requests.post(url=url, data=postdata)


def save_ledger(ledger, ledgerfile):
    with open(ledgerfile, 'w') as fp:
        json.dump(ledger, fp)


def transfer_file(fpath, transfer_location):
    # FIXME implement
    pass


def main():
    # text-file contains name and date of fn produced
    pssdir = sys.argv[1]
    ledgerfn = sys.argv[2]
    kantelehost = sys.argv[3]  # http://host.com/kantele
    client_id = sys.argv[4]
    transfer_location = sys.argv[5]
    with open(ledgerfn) as fp:
        ledger = json.load(fp)
    for fn in os.listdir(pssdir):
        with open(os.path.join(pssdir, fn)) as fp:
            prod_date, rawfilename = fp.read().strip().split('\t')
            if prod_date not in ledger:
                ledger[prod_date] = {'fpath': rawfilename, 'md5': False,
                                     'registered': False, 'transferred': False,
                                     'remote_ok': False}
                save_ledger(ledger, ledgerfn)
    for produced_fn in ledger.values():
        if not produced_fn['md5']:
            produced_fn['md5'] = md5(produced_fn['fpath'])
            save_ledger(ledger, ledgerfn)
    for prod_date, produced_fn in ledger.items():
        if not produced_fn['registered']:
            fn = os.path.basename(produced_fn['fpath'])
            size = os.path.getsize(produced_fn['fpath'])
            reg_response = register_file(kantelehost, fn, produced_fn['md5'],
                                         size, prod_date, client_id)
            print('REG response', reg_response)
            js_resp = json.loads(reg_response)
            # FIXME if reg_response is ok, json, and also add file_id returned
            if js_resp['state'] == 'registered':
                produced_fn['remote_id'] = js_resp['fn_id']
                produced_fn['registered'] = True
            save_ledger(ledger, ledgerfn)
    for produced_fn in ledger.values():
        if produced_fn['registered'] and not produced_fn['transferred']:
            try:
                transfer_file(produced_fn['fpath'], transfer_location)
            except RuntimeError:
                pass
            else:
                produced_fn['transferred'] = True
                save_ledger(ledger, ledgerfn)
    for produced_fn in ledger.values():
        if produced_fn['transferred'] and not produced_fn['remote_ok']:
            response = register_transfer(kantelehost, produced_fn['remote_id'],
                                         client_id)
            js_resp = json.loads(response)
            # FIXME if reg_response is ok, check for status code HTTP
            #json, and also x returned
            if not js_resp['md5_state']:
                continue
            elif js_resp['md5_state'] == 'error':
                produced_fn['transferred'] = False
            elif js_resp['md5_state'] == 'ok':
                produced_fn['remote_ok'] = True
            save_ledger(ledger, ledgerfn)
    for done_ledger_key in [k for k, x in ledger.items() if x['remote_ok']]:
        del(ledger[done_ledger_key])
    save_ledger(ledger, ledgerfn)


if __name__ == '__main__':
    main()
