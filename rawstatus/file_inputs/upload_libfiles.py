import os
import sys
import requests
import json
from urllib.parse import urljoin
from time import sleep

import producer as p

LEDGERFN = 'ledger.json'
KANTELEHOST = os.environ.get('KANTELEHOST')
CLIENT_ID = os.environ.get('CLIENT_ID')
KEYFILE = os.environ.get('KEYFILE')
SCP_FULL = os.environ.get('SCP_FULL')


def register_libraryfile(fn_item, ledger, ledgerfn, description, host, client_id):
    if not fn_item['library'] and fn_item['remote_ok']:
        url = urljoin(host, 'files/setlibrary/')
        postdata = {'fn_id': fn_item['remote_id'], 'client_id': client_id,
                    'desc': description}
        reg_response = requests.post(url=url, data=postdata)
        js_resp = reg_response.json()
        fn_item['library'] = js_resp['library']
    p.save_ledger(ledger, ledgerfn)


def check_transferred(fn_item, ledger, ledgerfn, kantelehost, url, client_id,
                      **getkwargs):
    while True:
        p.check_success_transferred_files(ledger, ledgerfn, kantelehost, url,
                                          client_id, **getkwargs)
        for file_done in [k for k, x in ledger.items() if x['remote_ok']]:
            file_done = ledger[file_done]['fpath']
#            logging.info('Finished with file {}: '
#                         '{}'.format(file_done, ledger[file_done]))
        p.save_ledger(ledger, ledgerfn)
        if fn_item['remote_ok']:
            break
        sleep(10)


def check_done(fn_item, ledger, ledgerfn, kantelehost, client_id, donebox):
    if not fn_item['library']:
        print('Problem creating a library from this file')
        return
    while True:
        url = urljoin(kantelehost, 'files/libfile/')
        params = {'fn_id': fn_item['remote_id']}
        reg_response = requests.get(url=url, params=params)
        js_resp = reg_response.json()
        if js_resp['library'] and js_resp['ready']:
            del(ledger[fn_item['fpath']])
            break
        sleep(10)
    p.save_ledger(ledger, ledgerfn)


def main():
    p.set_logger()
    fnpath = sys.argv[1]
    description = sys.argv[2]
    #ledgerfn = sys.argv[4]
    #kantelehost = sys.argv[5]  # http://host.com/kantele
    #client_id = sys.argv[6]
    #keyfile = sys.argv[7]
    #transfer_location = sys.argv[8]  # SCP login@storageserver.com:/home/store
    try:
        with open(LEDGERFN) as fp:
            ledger = json.load(fp)
    except IOError:
        ledger = {}
    if fnpath not in ledger:
        ledger[fnpath] = p.get_new_file_entry(fnpath)
        ledger[fnpath]['library'] = False
        p.save_ledger(ledger, LEDGERFN)
    if not ledger[fnpath]['md5']:
        ledger[fnpath]['md5'] = p.md5(fnpath)
    p.register_outbox_files(ledger, LEDGERFN, KANTELEHOST, 'files/register/', 
                CLIENT_ID, claimed=True)
    p.transfer_outbox_files(ledger, LEDGERFN, SCP_FULL, KEYFILE,
                              KANTELEHOST, CLIENT_ID)
    p.register_transferred_files(ledger, LEDGERFN, KANTELEHOST, CLIENT_ID)
    check_transferred(ledger[fnpath], ledger, LEDGERFN, KANTELEHOST, 'files/md5', CLIENT_ID)
    register_libraryfile(ledger[fnpath], ledger, LEDGERFN, description,
                         KANTELEHOST, CLIENT_ID)
    check_done(ledger[fnpath], ledger, LEDGERFN, KANTELEHOST, CLIENT_ID,
               os.path.split(fnpath)[0])


if __name__ == '__main__':
    main()
