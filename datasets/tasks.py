import os
import shutil
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task

from kantele import settings as config
from rawstatus import tasks as rstasks
from jobs.post import update_db

# Updating stuff in tasks happens over the API, assume no DB is touched. This
# avoids setting up auth for DB


@shared_task(bind=True)
def convert_to_mzml(self, fn, fnpath, servershare):
    """This will run on remote in other repo (proteomics-tasks) so there is no
    need to be no code in here, the task is an empty shell with only the
    task name"""
    return True


@shared_task(bind=True)
def scp_storage(self, mzmlfile, rawfn_id, dsetdir, servershare, reporturl):
    """This will run on remote in other repo (proteomics-tasks) so there is no
    need to be no code in here, the task is an empty shell with only the
    task name"""
    return True


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
    url = urljoin(config.KANTELEHOST, reverse('files:updatestorage'))
    try:
        update_db(url, postdata)
    except RuntimeError:
        # FIXME shutil.move(dst, src)
        raise


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def move_file_storage(self, fn, srcshare, srcpath, dstpath, fn_id):
    src = os.path.join(config.SHAREMAP[srcshare], srcpath, fn)
    dst = os.path.join(config.STORAGESHARE, dstpath, fn)
    print('Moving file {} to {}'.format(src, dst))
    dstdir = os.path.split(dst)[0]
    if not os.path.exists(dstdir):
        try:
            os.makedirs(dstdir)
        except FileExistsError:
            # Race conditions may happen
            pass
    elif not os.path.isdir(dstdir):
        raise RuntimeError('Directory {} is already on disk as a file name. '
                           'Not moving files.')
        # FIXME should update DB and set job to error
    shutil.move(src, dst)
    postdata = {'fn_id': fn_id, 'servershare': config.STORAGESHARENAME,
                'dst_path': dstpath, 'client_id': config.APIKEY,
                'task': self.request.id}
    url = urljoin(config.KANTELEHOST, reverse('files:updatestorage'))
    try:
        update_db(url, postdata)
    except RuntimeError:
        shutil.move(dst, src)
        raise
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
    url = urljoin(config.KANTELEHOST, reverse('files:updatestorage'))
    try:
        update_db(url, postdata)
    except RuntimeError:
        shutil.move(dst, src)
        raise
    print('File {} moved to tmp and DB updated'.format(fn_id))


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def md5_check_arrived_file(self, fnpath, servershare):
    fullpath = os.path.join(config.SHAREMAP[servershare], fnpath)
    print('Calculating MD5 for {}'.format(fullpath))
    try:
        dst_md5 = rstasks.calc_md5(fullpath)
    except:
        print('MD5 calculation failed, check file {}'.format(fullpath))
        self.retry(countdown=60)
    print('MD5 for {} is {}'.format(fullpath, dst_md5))
    return dst_md5
