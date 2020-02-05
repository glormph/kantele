import hashlib
import os
import requests
import subprocess
import zipfile
from ftplib import FTP
from urllib.parse import urljoin
from time import sleep
from datetime import datetime

from django.urls import reverse

from kantele import settings as config
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from jobs.post import update_db, taskfail_update_db


def calc_md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@shared_task(queue=config.QUEUE_PXDOWNLOAD, bind=True)
def download_px_file_raw(self, ftpurl, ftpnetloc, sf_id, raw_id, size, sharename, dset_id):
    """Downloads PX file, validate by file size, get MD5
    Uses separate queue on storage, because otherwise trouble when 
    needing the storage queue while downloading PX massive dsets.
    """
    print('Downloading PX dataset rawfile {}'.format(ftpurl))
    postdata = {'client_id': config.APIKEY, 'task': self.request.id,
                'sf_id': sf_id, 'raw_id': raw_id, 'dset_id': dset_id}
    fn = os.path.split(ftpurl)[1]
    dstfile = os.path.join(config.SHAREMAP[sharename], fn)
    try:
        with FTP(ftpnetloc) as ftp:
            ftp.login()
            ftp.retrbinary('RETR {}'.format(ftpurl), 
                           open(dstfile, 'wb').write)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    if os.path.getsize(dstfile) != size:
        print('Size of fn {} is not the same as source size {}'.format(dstfile, size))
        taskfail_update_db(self.request.id)
    try:
        postdata['md5'] = calc_md5(dstfile)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    url = urljoin(config.KANTELEHOST, reverse('jobs:downloadpx'))
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata)
            raise
    print('MD5 of {} is {}, registered in DB'.format(dstfile, postdata['md5']))


@shared_task(queue=config.QUEUE_STORAGE, bind=True)
def get_md5(self, source_md5, sfid, fnpath, servershare):
    # This should be run on the storage server
    """Checks MD5 of file and compares with source_md5. Report to host.
    If they do not match, host will set checked to False of storedfile
    """
    print('MD5 requested for file {}'.format(sfid))
    fnpath = os.path.join(config.SHAREMAP[servershare], fnpath)
    try:
        result = calc_md5(fnpath)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    postdata = {'sfid': sfid, 'md5': result, 'client_id': config.APIKEY,
                'task': self.request.id, 'source_md5': source_md5}
    url = urljoin(config.KANTELEHOST, reverse('jobs:setmd5'))
    msg = ('Could not update database: http/connection error {}. '
           'Retrying in one minute')
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise
    print('MD5 of {} is {}, registered in DB'.format(fnpath, result))
    return result


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def delete_file(self, servershare, filepath, fn_id):
    fileloc = os.path.join(config.SHAREMAP[servershare], filepath)
    try:
        os.remove(fileloc)
    except FileNotFoundError:
        # File is already deleted or just not where it is, pass for now,
        # will be registered as deleted
        pass
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    msg = ('Could not update database with deletion of fn {} :'
           '{}'.format(filepath, '{}'))
    url = urljoin(config.KANTELEHOST, reverse('jobs:deletefile'))
    postdata = {'sfid': fn_id, 'task': self.request.id,
                'client_id': config.APIKEY}
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(bind=True, queue=config.QUEUE_STORAGE)
def delete_empty_dir(self, servershare, directory):
    dirpath = os.path.join(config.SHAREMAP[servershare], directory)
    print('Trying to delete empty directory {}'.format(dirpath))
    try:
        os.rmdir(dirpath)
    except (OSError, Exception):
        # OSError raised on dir not empty
        taskfail_update_db(self.request.id)
        raise
    except FileNotFoundError:
        # Directory doesnt exist, no need to delete
        print('Directory did not exist, do not delete')
        pass
    msg = ('Could not update database with deletion of dir {} :'
           '{}'.format(dirpath, '{}'))
    url = urljoin(config.KANTELEHOST, reverse('jobs:rmdir'))
    postdata = {'task': self.request.id, 'client_id': config.APIKEY}
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(queue=config.QUEUE_STORAGE)
def unzip_folder(self, servershare, fnpath, sf_id):
    zipped_fn = os.path.join(config.SHAREMAP[servershare], fnpath)
    try:
        with zipfile.ZipFile(zipped_fn, 'r') as zipfp:
            zipfp.extractall(path=os.path.split(zipped_fn)[0])
    except zipfile.BadZipFile:
        taskfail_update_db(self.request.id)
        raise
    else:
        os.remove(zipped_fn)
    url = urljoin(config.KANTELEHOST, reverse('jobs:unzipped'))
    postdata = {'task': self.request.id, 'client_id': config.APIKEY}
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(bind=True, queue=config.QUEUE_PDC)
def pdc_archive(self, md5, yearmonth, servershare, filepath, fn_id):
    print('Archiving file {} to PDC tape'.format(filepath))
    basedir = config.SHAREMAP[servershare]
    fileloc = os.path.join(basedir, filepath)
    link = os.path.join(basedir, yearmonth, md5)
    try:
        os.makedirs(os.path.dirname(link))
    except FileExistsError:
        pass
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    try:
        os.symlink(fileloc, link)
    except FileExistsError:
        os.unlink(link)
        os.symlink(fileloc, link)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    # dsmc archive can be reran without error if file already exists
    # it will arvchive again
    cmd = ['dsmc', 'archive', link]
    env = os.environ
    env['DSM_DIR'] = config.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    postdata = {'sfid': fn_id, 'pdcpath': link,
                'task': self.request.id, 'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('jobs:createpdcarchive'))
    msg = ('Could not update database with for fn {} with PDC path {} :'
           '{}'.format(filepath, link, '{}'))
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            # FIXME this makes no sense, you cannot update DB
            update_db(url, postdata, msg)
            raise
    else:
        os.unlink(link)


@shared_task(bind=True, queue=config.QUEUE_PDC)
def pdc_restore(self, md5, yearmonth, servershare, filepath, fn_id):
    print('Restoring file {} to PDC tape'.format(filepath))
    basedir = config.SHAREMAP[servershare]
    fileloc = os.path.join(basedir, filepath)
    backupfile = os.path.join(basedir, yearmonth, md5)
    # Create dir for backup file (/home/storage/2019_05/)
    try:
        os.makedirs(os.path.dirname(backupfile))
    except FileExistsError:
        pass
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    # restore to tmplocation /home/storage/2019_05/abcd12345ae (md5)
    cmd = ['dsmc', 'restore', backupfile]
    env = os.environ
    env['DSM_DIR'] = config.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    # move file to proper location
    if os.path.exists(fileloc) and os.path.isfile(fileloc):
        print('Tried to move DSMC-restored tmpfile {} to target file {} but target already exists'.format(backupfile, fileloc))
    else:
        try:
            shutil.move(backupfile, fileloc)
        except Exception:
            try:
                self.retry(countdown=60)
            except MaxRetriesExceededError:
                taskfail_update_db(self.request.id)
                raise
    postdata = {'sfid': fn_id, 'task': self.request.id, 'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('jobs:restoredpdcarchive'))
    msg = ('Restore from archive could not update database with for fn {} with PDC path {} :'
           '{}'.format(filepath, link, '{}'))
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            raise


@shared_task(bind=True, queue=config.QUEUE_SWESTORE)
def swestore_upload(self, md5, servershare, filepath, fn_id):
    print('Uploading file {} to swestore'.format(filepath))
    fileloc = os.path.join(config.SHAREMAP[servershare], filepath)
    uri = os.path.join(config.SWESTORE_URI, md5)
    mountpath_fn = os.path.join(config.DAV_PATH, md5)
    # Check if proj folder exists on the /mnt/dav, mkdir if not
    # Dont upload using /mnt/dav, use curl
    curl = ['curl', '-1', '--location', 
            '--cert',  '{}:{}'.format(config.CERTLOC, config.CERTPASS),
            '--key', config.CERTKEYLOC, '-T', fileloc, uri]
    try:
        subprocess.check_call(curl)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    # if the upload is REALLY quick sometimes the DAV hasnt refreshed and you
    # will get filenotfound
    sleep(5)
    try:
        md5_upl = calc_md5(mountpath_fn)
    except FileNotFoundError:
        # could indicate no transfer, or dav not mounted
        # user needs to investigate and retry this
        print('Failed to get MD5 for Swestore upload of '
              '{}'.format(filepath))
        taskfail_update_db(self.request.id)
        raise
    else:
        if not md5_upl == md5:
            print('Swestore upload failed with incorrect MD5, retrying')
            taskfail_update_db(self.request.id)
            raise
        else:
            print('Successfully uploaded {} '
                  'with MD5 {}'.format(mountpath_fn, md5_upl))
    postdata = {'sfid': fn_id, 'swestore_path': uri,
                'task': self.request.id, 'client_id': config.APIKEY}
    url = urljoin(config.KANTELEHOST, reverse('jobs:createswestore'))
    msg = ('Could not update database with for fn {} with swestore URI {} :'
           '{}'.format(filepath, uri, '{}'))
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise
