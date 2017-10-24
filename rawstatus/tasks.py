import hashlib
import os
import requests
import subprocess
from urllib.parse import urljoin

from django.urls import reverse

from kantele import settings as config
from celery import shared_task


def calc_md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@shared_task(queue=config.QUEUE_STORAGE, bind=True)
def get_md5(self, sfid, fnpath, servershare):
    # This should be run on the storage server
    print('MD5 requested for file {}'.format(sfid))
    fnpath = os.path.join(config.SHAREMAP[servershare], fnpath)
    result = calc_md5(fnpath)
    postdata = {'sfid': sfid, 'md5': result, 'client_id': config.APIKEY,
                'task': self.request.id}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-setmd5'))
    try:
        r = requests.post(url=url, data=postdata)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = ('Could not update database: http/connection error {}. '
               'Retrying in one minute'.format(e))
        print(msg)
        self.retry(countdown=60)
    except:
        raise
    print('MD5 of {} is {}, registered in DB'.format(fnpath, result))
    return result


@shared_task(bind=True, queue=config.QUEUE_SWESTORE)
def swestore_upload(self, md5, servershare, filepath, fn_id):
    fileloc = os.path.join(config.SHAREMAP[servershare], filepath)
    print('Uploading file {} to swestore'.format(fileloc))
    uri = os.path.join(config.SWESTORE_URI, md5)
    mountpath_fn = os.path.join(config.DAV_PATH, md5)
    # Check if proj folder exists on the /mnt/dav, mkdir if not
    # Dont upload using /mnt/dav, use curl
    curl = ['curl', '-1', '--location', '--cacert', config.CACERTLOC,
            '--cert',  '{}:{}'.format(config.CERTLOC, config.CERTPASS),
            '--key', config.CERTKEYLOC, '-T', fileloc, uri]
    subprocess.check_call(curl)
    try:
        md5_upl = calc_md5(mountpath_fn)
    except FileNotFoundError:
        # could indicate no transfer, or dav not mounted
        # user needs to investigate and retry this
        print('Failed to get MD5 for Swestore upload of '
              '{}'.format(filepath))
        raise
    else:
        if not md5_upl == md5:
            print('Swestore upload failed with incorrect MD5, retrying')
            self.retry()
        else:
            print('Successfully uploaded {} '
                  'with MD5 {}'.format(mountpath_fn, md5_upl))
    postdata = {'sfid': fn_id, 'swestore_path': uri,
                'task': self.request.id, 'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-createswestore'))
    try:
        r = requests.post(url=url, data=postdata)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = ('Could not update database with for fn {} with swestore URI {} :'
               '{}'.format(filepath, uri, e))
        print(msg)
        self.retry()
