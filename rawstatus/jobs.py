import os
import requests
from urllib.parse import urlsplit
from datetime import datetime

from rawstatus import tasks, models
from datasets import tasks as dstasks
from jobs.post import create_db_task
from kantele import settings


def get_md5(job_id, sf_id):
    print('Running MD5 job')
    sfile = models.StoredFile.objects.filter(pk=sf_id).select_related(
        'servershare', 'rawfile').get()
    fnpath = os.path.join(sfile.path, sfile.filename)
    res = tasks.get_md5.delay(sfile.rawfile.source_md5, sfile.id, fnpath,
                              sfile.servershare.name)
    create_db_task(res.id, job_id, sfile.rawfile.source_md5, sfile.id, fnpath,
                   sfile.servershare.name)
    print('MD5 task queued')


def create_pdc_archive(job_id, sf_id, md5):
    print('Running swestore backup job')
    sfile = models.StoredFile.objects.filter(pk=sf_id).select_related(
        'servershare').get()
    yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
    # only create entry when not already exists, no sideeffects
    try:
        models.PDCBackedupFile.objects.get(storedfile=sfile)
    except models.PDCBackedupFile.DoesNotExist:
        models.PDCBackedupFile.objects.create(storedfile=sfile, 
                pdcpath='', success=False)
    fnpath = os.path.join(sfile.path, sfile.filename)
    res = tasks.pdc_archive.delay(md5, yearmonth, sfile.servershare.name, fnpath, sfile.id)
    create_db_task(res.id, job_id, md5, yearmonth, sfile.servershare.name, fnpath, sfile.id)
    print('PDC archival task queued')


def create_swestore_backup(job_id, sf_id, md5):
    print('Running swestore backup job')
    sfile = models.StoredFile.objects.filter(pk=sf_id).select_related(
        'servershare').get()
    # only create entry when not already exists, no sideeffects
    try:
        models.SwestoreBackedupFile.objects.get(storedfile=sfile)
    except models.SwestoreBackedupFile.DoesNotExist:
        models.SwestoreBackedupFile.objects.create(storedfile=sfile,
                                                   swestore_path='',
                                                   success=False)
    fnpath = os.path.join(sfile.path, sfile.filename)
    res = tasks.swestore_upload.delay(md5, sfile.servershare.name, fnpath,
                                      sfile.id)
    create_db_task(res.id, job_id, md5, sfile.servershare.name, fnpath, sfile.id)
    print('Swestore task queued')


def rename_file(job_id, fn_id, newname):
    """Only renames file inside same path/server. Does not move cross directories.
    This job checks if there is a RawFile entry with the same name in the same folder
    to avoid possible renaming collisions. Updates RawFile in job instead of view 
    since jobs are processed in a single queue.
    Since it only expects raw files it will also rename all mzML attached converted
    files. newname should NOT contain the file extension, only name.
    FIXME: make impossible to overwrite using move jobs at all (also moving etc)
    """
    fn = models.StoredFile.objects.select_related('rawfile', 'servershare').get(
        pk=fn_id)
    # FIXME task checks if src == dst, but we could do that already here?
    fn_ext = os.path.splitext(fn.filename)[1]
    if models.StoredFile.objects.exclude(pk=fn_id).filter(
            rawfile__name=newname + fn_ext, path=fn.path,
            servershare_id=fn.servershare_id).count():
        raise RuntimeError('A file in path {} with name {} already exists or will soon be created. Please choose another name'.format(fn.path, newname))
    fn.rawfile.name = newname + fn_ext
    fn.rawfile.save()
    for changefn in fn.rawfile.storedfile_set.all():
        oldname, ext = os.path.splitext(changefn.filename)
        special_type = '_refined' if changefn.filetype_id == settings.REFINEDMZML_SFGROUP_ID else ''
        print(newname, special_type)
        tid = dstasks.move_file_storage.delay(changefn.filename, changefn.servershare.name,
                                              changefn.path, changefn.path, changefn.id, 
                                              newname='{}{}{}'.format(newname, special_type, ext)).id
        create_db_task(tid, job_id, changefn.filename, changefn.servershare.name,
                       changefn.path, changefn.path, changefn.id, newname=newname + ext)


def move_single_file(job_id, fn_id, dst_path, oldname=False, dstshare=False, newname=False):
    fn = models.StoredFile.objects.select_related('rawfile', 'servershare').get(
        pk=fn_id)
    oldname = fn.filename if not oldname else oldname
    tid = dstasks.move_file_storage.delay(oldname, fn.servershare.name,
                                          fn.path, dst_path, fn.id, dstshare=dstshare,
                                          newname=newname).id
    create_db_task(tid, job_id, oldname, fn.servershare.name,
                   fn.path, dst_path, fn.id, dstshare=dstshare, newname=newname)


def delete_empty_directory(job_id, analysis_id, *dependent_sfids):
    """Check first if all the sfids are set to purged, indicating the dir is actually empty.
    Then queue a task. The sfids also make this job dependent on other jobs on those, as in
    the file-purging tasks before this directory deletion"""
    sfiles = models.StoredFile.objects.filter(pk__in=dependent_sfids)
    if sfiles.count() == sfiles.filter(purged=True).count():
        fn = sfiles.select_related('servershare').last()
        tid = tasks.delete_empty_dir.delay(fn.servershare.name, fn.path).id
        create_db_task(tid, job_id, fn.servershare.name, fn.path)
    else:
        raise RuntimeError('Cannot delete dir: according to the DB, there are still storedfiles which '
            'have not been purged yet in the directory')
        


def download_px_project_getfiles(dset_id, pxacc, rawfnids, sharename):
    """get only files that are NOT downloaded yet
    they will have: storedfile not checked, md5 == md5('fnstring')
    but maybe dont check last one
    """
    return models.StoredFile.objects.filter(rawfile_id__in=rawfnids, checked=False)


def call_proteomexchange(pxacc):
    prideurl = 'https://www.ebi.ac.uk/pride/ws/archive/file/list/project/{}'.format(pxacc)
    return [x for x in requests.get(prideurl).json()['list'] if x['fileType'] == 'RAW']


def download_px_project(job_id, dset_id, pxacc, rawfnids, sharename, *sf_ids):
    """gets sf_ids, of non-checked non-downloaded PX files.
    checks pride, fires tasks for files not yet downloaded. 
    """
    px_stored = {x.filename: x for x in models.StoredFile.objects.filter(
                     pk__in=sf_ids, checked=False).select_related('rawfile')}
    t_ids = []
    for fn in call_proteomexchange(pxacc):
        ftpurl = urlsplit(fn['downloadLink'])
        filename = os.path.split(ftpurl.path)[1]
        if filename in px_stored and fn['fileSize'] == px_stored[filename].rawfile.size:
            pxsf = px_stored[filename]
            t_ids.append(tasks.download_px_file_raw.delay(
                ftpurl.path, ftpurl.netloc, pxsf.id, pxsf.rawfile_id, fn['fileSize'],
                sharename, dset_id).id)
        create_db_task(t_ids[-1], job_id, ftpurl.path, ftpurl.netloc, pxsf.id,
                       pxsf.rawfile_id, fn['fileSize'], sharename, dset_id)
