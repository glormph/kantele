import hashlib
import os
import requests
from urllib.parse import urljoin

from django.urls import reverse

from kantele import settings as config
from celery import shared_task


@shared_task(queue=config.QUEUE_STORAGE, bind=True)
def get_md5(self, sfid, path, servershare, filename):
    # This should be run on the storage server
    print('MD5 requested for file {}'.format(sfid))
    # FIXME will not have django access to DB, use API to update, needs a login
    fnpath = os.path.join(config.SHAREMAP[servershare], path, filename)
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
