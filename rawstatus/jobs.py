import os

from rawstatus import tasks, models
from datasets import tasks as dstasks
from jobs.models import Task


def get_md5(job_id, sf_id):
    print('Running MD5 job')
    sfile = models.StoredFile.objects.filter(pk=sf_id).select_related(
        'servershare', 'rawfile').get()
    fnpath = os.path.join(sfile.path, sfile.filename)
    res = tasks.get_md5.delay(sfile.rawfile.source_md5, sfile.id, fnpath,
                              sfile.servershare.name)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')
    print('MD5 task queued')


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
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')
    print('Swestore task queued')


def move_single_file(job_id, fn_id, dst_path, newname=False):
    fn = models.StoredFile.objects.select_related('rawfile', 'servershare').get(
        pk=fn_id)
    tid = dstasks.move_file_storage.delay(fn.rawfile.name, fn.servershare.name,
                                          fn.path, dst_path, fn.id, newname).id
    Task.objects.create(asyncid=tid, job_id=job_id, state='PENDING')


def download_px_project(job_id, projectname, expname, user_id):
    tid = tasks.download_px_project_raw.delay(projectname, expname, user_id)
    Task.objects.create(asyncid=tid, job_id=job_id, state='PENDING')
