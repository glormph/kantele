import sys
import os
import shutil
import subprocess
from urllib.parse import urljoin
from time import sleep

from django.urls import reverse
from celery import shared_task

from kantele import settings as config
from rawstatus import tasks as rstasks
from jobs.post import update_db

# Updating stuff in tasks happens over the API, assume no DB is touched. This
# avoids setting up auth for DB

PROTEOWIZ_LOC = ('C:\Program Files\ProteoWizard\ProteoWizard '
                 '3.0.11336\msconvert.exe')
PSCP_LOC = ('C:\Program Files\PuTTY\pscp.exe')
RAWDUMPS = 'C:\\rawdump'
MZMLDUMPS = 'C:\\mzmldump'


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


@shared_task(bind=True)
def convert_to_mzml(self, fn, fnpath, servershare):
    fullpath = os.path.join(config.SHAREMAP[servershare], fnpath, fn)
    copy_infile(fullpath)
    if sys.platform.startswith("win"):
        # Don't display the Windows GPF dialog if the invoked program dies.
        # See comp.os.ms-windows.programmer.win32
        # How to suppress crash notification dialog?, Jan 14,2004 -
        # Raymond Chen's response [1]
        import ctypes
        SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
        ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)
        subprocess_flags = 0x8000000  # win32con.CREATE_NO_WINDOW?
    else:
        subprocess_flags = 0
    print('Received conversion command for file {0}'.format(fullpath))
    infile = os.path.join(RAWDUMPS, os.path.basename(fullpath))
    resultpath = os.path.join(
        MZMLDUMPS, os.path.splitext(os.path.basename(fullpath))[0] + '.mzML')
    command = [PROTEOWIZ_LOC, infile, '--filter', '"peakPicking true 2"',
               '--filter', '"precursorRefine"', '-o', MZMLDUMPS]
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               creationflags=subprocess_flags)
    (stdout, stderr) = process.communicate()
    if process.returncode != 0 or not os.path.exists(resultpath):
        print('Error in running msconvert:\n{}'.format(stdout))
        self.retry()
    try:
        check_mzml_integrity(resultpath)
    except RuntimeError as e:
        cleanup_files(infile, resultpath)
        self.retry(exc=e)
    cleanup_files(infile)
    return resultpath


def check_mzml_integrity(mzmlfile):
    """Checks if file is valid XML by parsing it"""
    # Quick and dirty with head and tail just to check it is not truncated
    with open(mzmlfile, 'rb') as fp:
        firstlines = fp.readlines(100)
        fp.seek(-100, 2)
        lastlines = fp.readlines()
    if ('indexedmzML' in ','.join([str(x) for x in firstlines]) and
            'indexedmzML' in ','.join([str(x) for x in lastlines])):
        return True
    else:
        raise RuntimeError('WARNING, conversion did not result in mzML file '
                           'with proper head and tail! Retrying conversion.')
    # FIXME maybe implement iterparsing if this is not enough.


@shared_task(bind=True)
def scp_storage(self, mzmlfile, rawfn_id, dsetdir, servershare):
    print('Got copy-to-storage command, calculating MD5 for file '
          '{}'.format(mzmlfile))
    mzml_md5 = rstasks.calc_md5(mzmlfile)
    print('Copying mzML file {} with md5 {} to storage'.format(
        mzmlfile, mzml_md5))
    storeserver = config.SHAREMAP[servershare]
    dstfolder = os.path.join(storeserver, dsetdir.replace('\\', '/'))
    dst = '{}@{}:{}'.format(config.SCP_LOGIN, storeserver, dstfolder)
    try:
        subprocess.check_call([PSCP_LOC, '-i', config.PUTTYKEY, mzmlfile, dst])
    except:
        # FIXME probably better to not retry? put in dead letter queue?
        # usually when this task has probelsm it is usually related to network
        # or corrupt file, both of which are not nice to retry
        self.retry(countdown=60)
    print('Copied file, checking MD5 remotely using nested task')
    md5res = md5_check_arrived_file.delay(
        os.path.join(dsetdir, os.path.basename(mzmlfile)), servershare)
    while not md5res.ready():
        sleep(30)
    dst_md5 = md5res.get()
    if not dst_md5 == mzml_md5:
        print('Destination MD5 {} is not same as source MD5 {}. Retrying in 60 '
              'seconds'.format(dst_md5, mzml_md5))
        self.retry(countdown=60)
    postdata = {'rawfile_id': rawfn_id, 'task': self.request.id, 'md5': dst_md5,
                'servershare': servershare, 'path': dsetdir,
                'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('files:createmzml'))
    try:
        update_db(url, postdata)
    except RuntimeError:
        self.retry()
    print('done and removing local file {}'.format(mzmlfile))
    os.remove(mzmlfile)


def cleanup_files(*files):
    for fpath in files:
        os.remove(fpath)


def copy_infile(remote_file):
    dst = os.path.join(RAWDUMPS, os.path.basename(remote_file))
    print('copying file to local dumpdir')
    try:
        shutil.copy(remote_file, dst)
    except Exception as e:
        try:
            cleanup_files(dst)
        # windows specific error
        except FileNotFoundError:
            pass
        raise RuntimeError('{} -- WARNING, could not copy input {} to local '
                           'disk'.format(e, dst))
    print('Done copying file to local dumpdir')
