import os
import shutil
import requests
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task

from kantele import settings as config


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def move_file_storage(self, fn, srcshare, srcpath, dstpath, fn_id):
    src = os.path.join(config.SHAREMAP[srcshare], srcpath, fn)
    dst = os.path.join(config.STORAGESHARE, dstpath, fn)
    print('Moving file {} to {}'.format(src, dst))
    dstdir = os.path.split(dst)[0]
    if not os.path.exists(dst) or not os.path.isdir(dstdir):
        os.makedirs(dstdir)
    shutil.move(src, dst)
    # FIXME login
    postdata = {'fn_id': fn_id, 'servershare': config.STORAGESHARENAME,
                'dst_path': dstpath}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-updatestorage'))
    req = requests.post(url=url, data=postdata)
    if not req.status_code == 200:
        msg = 'Could not update database: http {}'.format(req.status_code)
        print(msg)
        shutil.move(dst, src)
        raise RuntimeError(msg)
    print('File {} moved to {}'.format(fn_id, dst))


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def move_stored_file_tmp(self, fn, path, fn_id):
    src = os.path.join(config.STORAGESHARE, path, fn)
    dst = os.path.join(config.TMPSHARE, fn)
    print('Moving stored file {} to tmp'.format(fn_id))
    shutil.move(src, dst)
    # FIXME API call to add new path to db, MV BACK IF HTTP NOT 200
    postdata = {'fn_id': fn_id, 'servershare': config.TMPSHARENAME,
                'dst_path': ''}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-updatestorage'))
    try:
        req = requests.post(url=url, data=postdata)
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError):
        msg = 'Could not update database: http {}'.format(req.status_code)
        print(msg)
        shutil.move(dst, src)
        raise RuntimeError(msg)
    print('File {}  moved to tmp'.format(fn_id))
