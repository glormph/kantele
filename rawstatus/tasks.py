import hashlib
import os
import requests
import subprocess
from urllib.parse import urljoin

from django.urls import reverse

from kantele import settings as config
from celery import shared_task


@shared_task(queue=config.QUEUE_STORAGE, bind=True)
def get_md5(self, sfid, fnpath, servershare):
    # This should be run on the storage server
    print('MD5 requested for file {}'.format(sfid))
    # FIXME will not have django access to DB, use API to update, needs a login
    fnpath = os.path.join(config.SHAREMAP[servershare], fnpath)
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    result = hash_md5.hexdigest()
    postdata = {'sfid': sfid, 'md5': result}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-setmd5'))
    req = requests.post(url=url, data=postdata)
    if not req.status_code == 200:
        print('Could not update database: http {}. Retrying in one '
              'minute'.format(req.status_code))
        self.retry(countdown=60)
    print('MD5 of {} is {}, registered in DB'.format(fnpath, result))
    return result


@shared_task(bind=True, queue=config.QUEUE_SWESTORE)
def swestore_upload(self, md5, servershare, filepath, fn_id):
    fileloc = os.path.join(config.SHAREMAP[servershare], filepath)
    print('Uploading file {} to swestore'.format(fileloc))
    uri = os.path.join(config.SWESTORE_BILS_BASE, md5)
    mountpath_fn = os.path.join(config.DAV_PATH, md5)
    # Check if proj folder exists on the /mnt/dav, mkdir if not
    # Dont upload using /mnt/dav, use curl
    curl = ['curl', '-1', '--location', '--cacert', config.CACERTLOC,
            '--cert',  '{}:{}'.format(config.CERTLOC, config.CERTPASS),
            '--key', config.CERTKEYLOC, '-T', fileloc, uri]
    subprocess.check_call(curl)
    try:
        md5_upl = subprocess.check_output(['md5sum',
                                           mountpath_fn]).split()[0]
    except subprocess.CalledProcessError:  # most likely file not found
        # could indicate no transfer, or dav not mounted
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
    postdata = {'sfid': fn_id, 'swestore_path': uri}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-createswestore'))
    try:
        requests.post(url=url, data=postdata)
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = 'Could not update database with for fn {} with swestore URI {} :'
        '{}'.format(filepath, uri, e)
        print(msg)
        self.retry()
