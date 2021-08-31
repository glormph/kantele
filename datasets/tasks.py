import os
import shutil
import subprocess
from urllib.parse import urljoin

from django.urls import reverse
from celery import shared_task

from kantele import settings
from jobs.post import update_db, taskfail_update_db
from analysis.tasks import prepare_nextflow_run, run_nextflow, transfer_resultfiles
from rawstatus.tasks import calc_md5

# Updating stuff in tasks happens over the API, assume no DB is touched. This
# avoids setting up auth for DB


@shared_task(bind=True)
def convert_to_mzml(self, fn, fnpath, outfile, sf_id, servershare, filtopts, reporturl, failurl):
    """This will run on remote in other repo (proteomics-tasks) so there is no
    need to be no code in here, the task is an empty shell with only the
    task name"""
    return True


@shared_task(bind=True)
def scp_storage(self, mzmlfile, rawfn_id, dsetdir, servershare, reporturl, failurl):
    """This will run on remote in other repo (proteomics-tasks) so there is no
    need to be no code in here, the task is an empty shell with only the
    task name"""
    return True


@shared_task(bind=True, queue=settings.QUEUE_NXF)
def run_convert_mzml_nf(self, run, params, raws, **kwargs):
    postdata = {'client_id': settings.APIKEY, 'task': self.request.id}
    runname = '{}_convert_mzml_{}'.format(run['dset_id'], run['timestamp'])
    run['runname'] = runname
    baserundir = settings.NF_RUNDIRS[run.get('nfrundirname', 'small')]
    rundir = os.path.join(baserundir, runname).replace(' ', '_')
    params, gitwfdir, stagedir = prepare_nextflow_run(run, self.request.id, rundir, {'--raws': raws}, [], params)
    profiles = 'docker,lehtio' # TODO put in deploy/settings
    try:
        run_nextflow(run, params, rundir, gitwfdir, profiles, '20.01.0')
    except subprocess.CalledProcessError as e:
        # FIXME report stderr with e
        errmsg = 'OUTPUT:\n{}\nERROR:\n{}'.format(e.stdout, e.stderr)
        taskfail_update_db(self.request.id, errmsg)
        raise RuntimeError('Error occurred converting mzML files: '
                           '{}\n\nERROR MESSAGE:\n{}'.format(rundir, errmsg))
    transfer_url = urljoin(settings.KANTELEHOST, reverse('jobs:mzmlfiledone'))
    resultfiles = {}
    for raw in raws:
        fname = os.path.splitext(raw[2])[0] + '.mzML'
        fpath = os.path.join(rundir, 'output', fname)
        resultfiles[fpath] = {'md5': calc_md5(fpath), 'file_id': raw[3], 'newname': fname}
    transfer_resultfiles((settings.ANALYSISSHARENAME, 'mzmls_in'), runname, resultfiles, transfer_url, self.request.id)
    url = urljoin(settings.KANTELEHOST, reverse('jobs:updatestorage'))
    update_db(url, json=postdata)
    shutil.rmtree(rundir)
    shutil.rmtree(stagedir)


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def rename_top_level_project_storage_dir(self, srcname, newname, proj_id):
    """Renames a project, including the below experiments/datasets"""
    msg = False
    srcpath = os.path.join(settings.STORAGESHARE, srcname)
    dstpath = os.path.join(settings.STORAGESHARE, newname)
    if not os.path.exists(path):
        msg = f'Cannot move project name {srcname} to {newname}, does not exist'
    elif not os.path.isdir(path):
        msg = f'Cannot move project name {srcname} to {newname}, {srcname} is not a directory'
    elif os.path.exists(dstpath):
        msg = f'Cannot move project name {srcname} to {newname}, already exists'
    if msg:
        taskfail_update_db(self.request.id, msg)
        raise RuntimeError(msg)
    try:
        shutil.move(srcpath, dstpath)
    except Exception:
        taskfail_update_db(self.request.id, msg='Failed renaming project for unknown reason')
        raise
    postdata = {'proj_id': proj_id, 'newname': newname,
            'task': self.request.id, 'client_id': settings.APIKEY}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:renameproject'))
    update_db(url, json=postdata)


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def rename_dset_storage_location(self, srcpath, dstpath, dset_id, sf_ids):
    """This expects one dataset per dir, as it will rename the whole dir"""
    print('Renaming dataset storage {} to {}'.format(srcpath, dstpath))
    try:
        shutil.move(os.path.join(settings.STORAGESHARE, srcpath), os.path.join(settings.STORAGESHARE, dstpath))
    except:
        taskfail_update_db(self.request.id)
        raise
    # Go through dirs in path and delete empty ones caused by move
    splitpath = srcpath.split(os.sep)
    for pathlen in range(0, len(splitpath))[::-1]:
        # no rmdir on the leaf dir (would be pathlen+1) since that's been moved
        checkpath = os.path.join(settings.STORAGESHARE, os.sep.join(splitpath[:pathlen]))
        if not os.listdir(checkpath):
            try:
                os.rmdir(checkpath)
            except:
                taskfail_update_db(self.request.id)
                raise
    fn_postdata = {'fn_ids': sf_ids, 'dst_path': dstpath, 
            'client_id': settings.APIKEY}
    ds_postdata = {'storage_loc': dstpath, 'dset_id': dset_id, 
            'task': self.request.id, 'client_id': settings.APIKEY}
    fnurl = urljoin(settings.KANTELEHOST, reverse('jobs:updatestorage'))
    dsurl = urljoin(settings.KANTELEHOST, reverse('jobs:update_ds_storage'))
    try:
        update_db(fnurl, json=fn_postdata)
        update_db(dsurl, json=ds_postdata)
    except RuntimeError:
        # FIXME cannot move back shutil.move(dst, src)
        raise


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def move_file_storage(self, fn, srcshare, srcpath, dstpath, fn_id, dstshare=False, newname=False):
    src = os.path.join(settings.SHAREMAP[srcshare], srcpath, fn)
    if not dstshare:
        dstshare = settings.STORAGESHARENAME
    if not newname:
        newname = fn
    dst = os.path.join(settings.SHAREMAP[dstshare], dstpath, newname)
    url = urljoin(settings.KANTELEHOST, reverse('jobs:updatestorage'))
    if src == dst:
        print('Source and destination are identical, not moving file')
        update_db(url, json={'client_id': settings.APIKEY, 'task': self.request.id})
    print('Moving file {} to {}'.format(src, dst))
    dstdir = os.path.split(dst)[0]
    if not os.path.exists(dstdir):
        try:
            os.makedirs(dstdir)
        except FileExistsError:
            # Race conditions may happen, dir already made by other task
            pass
        except Exception:
            taskfail_update_db(self.request.id)
            raise
    elif not os.path.isdir(dstdir):
        taskfail_update_db(self.request.id)
        raise RuntimeError('Directory {} is already on disk as a file name. '
                           'Not moving files.')
    try:
        shutil.move(src, dst)
    except Exception as e:
        taskfail_update_db(self.request.id)
        raise RuntimeError('Could not move file tot storage:', e)
    postdata = {'fn_id': fn_id, 'servershare': dstshare,
                'dst_path': dstpath, 'newname': os.path.basename(dst),
                'client_id': settings.APIKEY, 'task': self.request.id}
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        shutil.move(dst, src)
        raise
    print('File {} moved to {}'.format(fn_id, dst))


@shared_task(bind=True, queue=settings.QUEUE_STORAGE)
def move_stored_file_tmp(self, fn, path, fn_id):
    src = os.path.join(settings.STORAGESHARE, path, fn)
    dst = os.path.join(settings.TMPSHARE, fn)
    print('Moving stored file {} to tmp'.format(fn_id))
    try:
        shutil.move(src, dst)
    except Exception:
        taskfail_update_db(self.request.id)
        raise
    postdata = {'fn_id': fn_id, 'servershare': settings.TMPSHARENAME,
                'dst_path': '', 'client_id': settings.APIKEY,
                'task': self.request.id}
    url = urljoin(settings.KANTELEHOST, reverse('jobs:updatestorage'))
    try:
        update_db(url, json=postdata)
    except RuntimeError:
        shutil.move(dst, src)
        raise
    print('File {} moved to tmp and DB updated'.format(fn_id))
