import os
import shutil
import requests
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task

from kantele import settings as config

# Updating stuff in tasks happens over the API, assume no DB is touched. This
# avoids setting up auth for DB


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def rename_storage_location(self, srcpath, dstpath, storedfn_ids):
    print('Renaming dataset storage {} to {}'.format(srcpath, dstpath))
    dsttree = config.STORAGESHARE
    for srcdir, dstdir in zip(srcpath.split(os.sep), dstpath.split(os.sep)):
        if srcdir != dstdir:
            shutil.move(os.path.join(dsttree, srcdir),
                        os.path.join(dsttree, dstdir))
        dsttree = os.path.join(dsttree, dstdir)
    postdata = {'fn_ids': storedfn_ids, 'dst_path': dstpath,
                'task': self.request.id, 'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-updatestorage'))
    try:
        r = requests.post(url=url, data=postdata)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = 'Could not update database: {}'.format(e)
        print(msg)
        # FIXME shutil.move(dst, src)
        raise RuntimeError(msg)


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def move_file_storage(self, fn, srcshare, srcpath, dstpath, fn_id):
    src = os.path.join(config.SHAREMAP[srcshare], srcpath, fn)
    dst = os.path.join(config.STORAGESHARE, dstpath, fn)
    print('Moving file {} to {}'.format(src, dst))
    dstdir = os.path.split(dst)[0]
    if not os.path.exists(dstdir) or not os.path.isdir(dstdir):
        os.makedirs(dstdir)
    shutil.move(src, dst)
    postdata = {'fn_id': fn_id, 'servershare': config.STORAGESHARENAME,
                'dst_path': dstpath, 'client_id': config.APIKEY,
                'task': self.request.id}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-updatestorage'))
    try:
        r = requests.post(url=url, data=postdata)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = 'Could not update database: {}'.format(e)
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
    postdata = {'fn_id': fn_id, 'servershare': config.TMPSHARENAME,
                'dst_path': '', 'client_id': config.APIKEY,
                'task': self.request.id}
    url = urljoin(config.KANTELEHOST, reverse('rawstatus-updatestorage'))
    try:
        r = requests.post(url=url, data=postdata)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        msg = 'Could not update database: {}'.format(e)
        print(msg)
        shutil.move(dst, src)
        raise RuntimeError(msg)
    print('File {} moved to tmp and DB updated'.format(fn_id))
