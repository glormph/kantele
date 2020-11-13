import hashlib
import os
import requests
import shutil
import subprocess
import zipfile
from ftplib import FTP
from urllib.parse import urljoin
from time import sleep
from datetime import datetime

from django.urls import reverse

from kantele import settings
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from jobs.post import update_db, taskfail_update_db


def calc_md5(fnpath):
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@shared_task(queue=settings.QUEUE_SEARCH_INBOX)
def search_raws_downloaded(serversharename, dirname):
    print('Scanning {} folder {} for import raws'.format(serversharename, dirname))
    raw_paths_found = []
    fullpath = os.path.join(settings.SHAREMAP[serversharename], dirname)
    for wpath, subdirs, files in os.walk(fullpath):
        raws = [x for x in files if os.path.splitext(x)[1].lower() == '.raw']
        if len(raws):
            dirname = os.path.relpath(wpath, fullpath)
            raw_paths_found.append({'dirname': dirname, 
                'files': [(os.path.join(dirname, x), os.path.getsize(os.path.join(fullpath, wpath, x)))
                    for x in files]})
    return raw_paths_found


@shared_task(queue=settings.QUEUE_PXDOWNLOAD, bind=True)
def register_downloaded_external_raw(self, fpath, sf_id, raw_id, sharename, dset_id):
    """Downloaded external files on inbox somewhere get MD5 checked and associate
    with a dataset
    """
    print('Registering external rawfile {}'.format(os.path.basename(fpath)))
    postdata = {'client_id': settings.APIKEY, 'task': self.request.id,
                'sf_id': sf_id, 'raw_id': raw_id, 'dset_id': dset_id}
    dstfile = os.path.join(settings.SHAREMAP[sharename], fpath)
    try:
        postdata['md5'] = calc_md5(dstfile)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    url = urljoin(settings.KANTELEHOST, reverse('jobs:register_external'))
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata)
            raise
    print('MD5 of {} is {}, registered in DB'.format(dstfile, postdata['md5']))


@shared_task(queue=settings.QUEUE_PXDOWNLOAD, bind=True)
def download_px_file_raw(self, ftpurl, ftpnetloc, sf_id, raw_id, size, sharename, dset_id):
    """Downloads PX file, validate by file size, get MD5
    Uses separate queue on storage, because otherwise trouble when 
    needing the storage queue while downloading PX massive dsets.
    """
    print('Downloading PX dataset rawfile {}'.format(ftpurl))
    postdata = {'client_id': settings.APIKEY, 'task': self.request.id,
                'sf_id': sf_id, 'raw_id': raw_id, 'dset_id': dset_id}
    fn = os.path.split(ftpurl)[1]
    dstfile = os.path.join(settings.SHAREMAP[sharename], fn)
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
    url = urljoin(settings.KANTELEHOST, reverse('jobs:register_external'))
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata)
            raise
    print('MD5 of {} is {}, registered in DB'.format(dstfile, postdata['md5']))


@shared_task(queue=settings.QUEUE_STORAGE, bind=True)
def get_md5(self, source_md5, sfid, fnpath, servershare):
    # This should be run on the storage server
    """Checks MD5 of file and compares with source_md5. Report to host.
    If they do not match, host will set checked to False of storedfile
    """
    print('MD5 requested for file {}'.format(sfid))
    fnpath = os.path.join(settings.SHAREMAP[servershare], fnpath)
    try:
        result = calc_md5(fnpath)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    postdata = {'sfid': sfid, 'md5': result, 'client_id': settings.APIKEY,
                'task': self.request.id, 'source_md5': source_md5}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:setmd5'))
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


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def delete_file(self, servershare, filepath, fn_id):
    fileloc = os.path.join(settings.SHAREMAP[servershare], filepath)
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
    url = urljoin(settings.KANTELEHOST, reverse('jobs:deletefile'))
    postdata = {'sfid': fn_id, 'task': self.request.id,
                'client_id': settings.APIKEY}
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def delete_empty_dir(self, servershare, directory):
    """Deletes the (reportedly) empty directory, then proceeds to delete any
    parent directory which is also empty"""
    dirpath = os.path.join(settings.SHAREMAP[servershare], directory)
    print('Trying to delete empty directory {}'.format(dirpath))
    try:
        os.rmdir(dirpath)
    except FileNotFoundError:
        # Directory doesnt exist, no need to delete
        print('Directory did not exist, do not delete')
    except (OSError, Exception):
        # OSError raised on dir not empty
        taskfail_update_db(self.request.id)
        raise
    # Now delete parent directories if any empty
    while os.path.split(directory)[0]:
        directory = os.path.split(directory)[0]
        dirpath = os.path.join(settings.SHAREMAP[servershare], directory)
        print('Trying to delete parent directory {}'.format(dirpath))
        try:
            os.rmdir(dirpath)
        except OSError:
            # OSError raised on dir not empty
            print('Parent directory {} not empty, stop deletion'.format(dirpath))
    # Report
    msg = ('Could not update database with deletion of dir {} :'
           '{}'.format(dirpath, '{}'))
    url = urljoin(settings.KANTELEHOST, reverse('jobs:rmdir'))
    postdata = {'task': self.request.id, 'client_id': settings.APIKEY}
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def unzip_folder(self, servershare, fnpath, sf_id):
    zipped_fn = os.path.join(settings.SHAREMAP[servershare], fnpath)
    unzippath = os.path.join(os.path.split(zipped_fn)[0], os.path.splitext(zipped_fn)[0])
    try:
        with zipfile.ZipFile(zipped_fn, 'r') as zipfp:
            zipfp.extractall(path=unzippath)
    except zipfile.BadZipFile:
        taskfail_update_db(self.request.id)
        raise
    else:
        os.remove(zipped_fn)
    url = urljoin(settings.KANTELEHOST, reverse('jobs:unzipped'))
    postdata = {'task': self.request.id, 'client_id': settings.APIKEY, 'sfid': sf_id}
    msg = ('Could not update database for unzipping fn {}. '
           '{}'.format(fnpath, '{}'))
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            update_db(url, postdata, msg)
            raise


@shared_task(bind=True, queue=settings.QUEUE_PDC)
def pdc_archive(self, md5, yearmonth, servershare, filepath, fn_id):
    print('Archiving file {} to PDC tape'.format(filepath))
    basedir = settings.SHAREMAP[servershare]
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
    env['DSM_DIR'] = settings.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError as CPE:
        if CPE.returncode != 8:
            # exit code 8 is "there are warnings but no problems"
            taskfail_update_db(self.request.id)
            raise
    postdata = {'sfid': fn_id, 'pdcpath': link,
                'task': self.request.id, 'client_id': settings.APIKEY}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:createpdcarchive'))
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
        try:
            os.rmdir(os.path.dirname(link))
        except OSError: # directory not empty
            pass


@shared_task(bind=True, queue=settings.QUEUE_PDC)
def pdc_restore(self, servershare, filepath, pdcpath, fn_id):
    print('Restoring file {} from PDC tape'.format(filepath))
    basedir = settings.SHAREMAP[servershare]
    fileloc = os.path.join(basedir, filepath)
    # restore to fileloc
    cmd = ['dsmc', 'retrieve', '-replace=no', pdcpath, fileloc]
    env = os.environ
    env['DSM_DIR'] = settings.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError as CPE:
        # exit code 4 is output when file already exist (we have replace=no)
        if CPE.returncode != 4:
            taskfail_update_db(self.request.id)
            raise
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    postdata = {'sfid': fn_id, 'task': self.request.id, 'client_id': settings.APIKEY}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:restoredpdcarchive'))
    msg = ('Restore from archive could not update database with for fn {} with PDC path {} :'
           '{}'.format(filepath, pdcpath, '{}'))
    try:
        update_db(url, postdata, msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            raise


@shared_task(bind=True, queue=settings.QUEUE_SWESTORE)
def swestore_upload(self, md5, servershare, filepath, fn_id):
    print('Uploading file {} to swestore'.format(filepath))
    fileloc = os.path.join(settings.SHAREMAP[servershare], filepath)
    uri = os.path.join(settings.SWESTORE_URI, md5)
    mountpath_fn = os.path.join(settings.DAV_PATH, md5)
    # Check if proj folder exists on the /mnt/dav, mkdir if not
    # Dont upload using /mnt/dav, use curl
    curl = ['curl', '-1', '--location', 
            '--cert',  '{}:{}'.format(settings.CERTLOC, settings.CERTPASS),
            '--key', settings.CERTKEYLOC, '-T', fileloc, uri]
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
            raise RuntimeError('Swestore upload failed with incorrect MD5, retrying')
        else:
            print('Successfully uploaded {} '
                  'with MD5 {}'.format(mountpath_fn, md5_upl))
    postdata = {'sfid': fn_id, 'swestore_path': uri,
                'task': self.request.id, 'client_id': settings.APIKEY}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:createswestore'))
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
