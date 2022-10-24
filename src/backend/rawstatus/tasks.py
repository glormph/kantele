import hashlib
import os
import requests
import shutil
import subprocess
import zipfile
from ftplib import FTP
from urllib.parse import urljoin, urlsplit
from time import sleep
from datetime import datetime
from tempfile import NamedTemporaryFile

from django.urls import reverse

from kantele import settings
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from jobs.post import update_db, taskfail_update_db


def calc_sha1(fnpath):
    """Need SHA1 to verify checksums from ProteomeXchange"""
    hash_sha = hashlib.sha1()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_sha.update(chunk)
    return hash_sha.hexdigest()


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


@shared_task(queue=settings.QUEUE_FILE_DOWNLOAD, bind=True)
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


@shared_task(queue=settings.QUEUE_FILE_DOWNLOAD, bind=True)
def download_px_file_raw(self, ftpurl, ftpnetloc, sf_id, raw_id, shasum, size, sharename, dset_id):
    """Downloads PX file, validate by file size and SHA1, get MD5.
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
    if calc_sha1(dstfile) != shasum:
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


@shared_task(queue=settings.QUEUE_FILE_DOWNLOAD, bind=True)
def rsync_transfer_file(self, sfid, srcpath, dstpath, dstsharename, do_unzip, stablefiles):
    '''Uses rsync to transfer uploaded file from KANTELEHOST/other RSYNC_HOST to storage server.
    In case of a zipped folder transfer, the file is unzipped and an MD5 check is done 
    on its relevant file, in case the transferred file is corrupt'''
    # FIXME need to take care of e.g. zipped uploads which do not contain relevant file
    # (use case e.g. microscopy images), unlike e.g. .d folders from Bruker.
    ssh_host = urlsplit(settings.KANTELEHOST).netloc
    ssh_srcpath = f'{settings.RSYNC_SSHUSER}@{ssh_host}:{srcpath}'
    dstfpath = os.path.join(settings.SHAREMAP[dstsharename], dstpath)
    cmd = ['rsync', '-avz', '-e',
            f'ssh -o StrictHostKeyChecking=no -p {settings.RSYNC_SSHPORT} -i {settings.RSYNC_SSHKEY}',
            ssh_srcpath, dstfpath]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            taskfail_update_db(self.request.id)
            raise
    postdata = {'sf_id': sfid, 'client_id': settings.APIKEY, 'task': self.request.id, 
            'do_md5check': do_md5check, 'unzipped': do_unzip}
    if do_unzip:
        # Unzip if needed, in that case recheck MD5 to be sure of the zipping has been correct
        # since MD5 is from internal file
        unzippath = os.path.join(os.path.split(dstfpath)[0], os.path.splitext(dstfpath)[0])
        try:
            with zipfile.ZipFile(dstfpath, 'r') as zipfp:
                zipfp.extractall(path=unzippath)
        except zipfile.BadZipFile:
            # Re queue zip and transfer!
            taskfail_update_db(self.request.id, msg='File to unzip had a problem and could be '
            'corrupt or partially transferred, could not unzip it')
            raise
        except IsADirectoryError:
            # file has already been transferred and we are instructed to re-unzip
            # possibly there is another zipped file
            taskfail_update_db(self.request.id, msg='File to unzip was a directory, has '
                    'likely already been unzipped and possibly been retransferred')
            raise
        except Exception:
            taskfail_update_db(self.request.id, msg='Unknown problem happened during '
                    'unzipping')
            raise
        else:
            os.remove(dstfpath)
        # now find stable file in zip to get MD5 on, do md5 check if needed
        ok_sf = [x for x in stablefiles if os.path.exists(os.path.join(unzippath, x))]
        if len(stablefiles) and not len(ok_sf):
            errmsg = 'Could not find stable file inside unzipped folder for MD5 calculation'
            taskfail_update_db(self.request.id, msg=errmsg)
            raise RuntimeError(errmsg)
        elif len(ok_sf):
            try:
                md5result = calc_md5(os.path.join(unzippath, stable_fn))
            except Exception:
                taskfail_update_db(self.request.id, msg='MD5 calculation failed')
                raise
            postdata.update({'md5': md5result})
    # Done, notify database
    url = urljoin(settings.KANTELEHOST, reverse('jobs:download_file'))
    msg = f'Rsync used for file transfer of {dstfpath} with id {sfid} to storage'
    try:
        update_db(url, json=postdata, msg=msg)
    except RuntimeError:
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            #update_db(url, json=postdata, msg=msg)
            raise
    print(msg)


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def delete_file(self, servershare, filepath, fn_id):
    print('Deleting file {} on {}'.format(filepath, servershare))
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


@shared_task(bind=True, queue=settings.QUEUE_PDC)
def pdc_archive(self, md5, yearmonth, servershare, filepath, fn_id, isdir):
    print('Archiving file {} to PDC tape'.format(filepath))
    basedir = settings.SHAREMAP[servershare]
    fileloc = os.path.join(basedir, filepath)
    if not os.path.exists(fileloc):
        taskfail_update_db(self.request.id, msg='Cannot find file to archive: {}'.format(fileloc))
        return
    link = os.path.join(settings.BACKUPSHARE, yearmonth, md5)
    linkdir = os.path.dirname(link)
    try:
        os.makedirs(linkdir)
    except FileExistsError:
        pass
    except Exception:
        taskfail_update_db(self.request.id, msg='Cannot create linkdir for archiving {}'.format(linkdir))
        raise
    try:
        os.symlink(fileloc, link)
    except FileExistsError:
        os.unlink(link)
        os.symlink(fileloc, link)
    except Exception:
        taskfail_update_db(self.request.id, msg='Cannot create symlink {} on file {} for '
            'archiving'.format(link, fileloc))
        raise
    # dsmc archive can be reran without error if file already exists
    # it will arvchive again
    if isdir:
        linkpath = os.path.join(link, '') # append a slash
        cmd = ['dsmc', 'archive', linkpath, '-subdir=yes']
    else:
        cmd = ['dsmc', 'archive', link]
    env = os.environ
    env['DSM_DIR'] = settings.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError as CPE:
        if CPE.returncode != 8:
            # exit code 8 is "there are warnings but no problems"
            taskfail_update_db(self.request.id, msg='There was a problem archiving the file {} '
                    'exit code was {}'.format(fileloc, CPE.returncode))
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
def pdc_restore(self, servershare, filepath, pdcpath, fn_id, isdir):
    print('Restoring file {} from PDC tape'.format(filepath))
    basedir = settings.SHAREMAP[servershare]
    fileloc = os.path.join(basedir, filepath)
    # restore to fileloc
    if isdir:
        dstpath = os.path.join(settings.BACKUPSHARE, 'retrievals', '') # with slash
        if not os.path.exists(dstpath):
            os.makedirs(dstpath)
        pdcdirpath = os.path.join(pdcpath, '') # append a slash
        cmd = ['dsmc', 'retrieve', '-subdir=yes', '-replace=no', pdcdirpath, dstpath]
    else:
        cmd = ['dsmc', 'retrieve', '-replace=no', pdcpath, fileloc]
    env = os.environ
    env['DSM_DIR'] = settings.DSM_DIR
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError as CPE:
        # exit code 4 is output when file already exist (we have replace=no)
        if CPE.returncode != 4:
            taskfail_update_db(self.request.id, 'Retrieving archive by DSMC failed for file '
                '{}, exit code was {}'.format(fileloc, CPE.returncode))
            raise
    except Exception:
        taskfail_update_db(self.request.id, 'DSMC retrieve command succeeded, but errors occurred '
            'when retrieving archive by DSMC failed for file {}'.format(fileloc, CPE.returncode))
        raise
    if isdir:
        basename_pdcpath = os.path.basename(pdcpath)
        try:
            shutil.move(os.path.join(dstpath, basename_pdcpath), fileloc)
        except Exception:
            taskfail_update_db(self.request.id, msg='File {} to retrieve from backup is directory '
            'type, it is retrieved to {} but errored when moving from there'.format(fileloc, pdcpath))
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
