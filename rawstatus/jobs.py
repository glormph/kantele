from celery import chain
import os

from rawstatus import tasks, models
from jobs.models import Task


def get_md5(job_id, sf_id):
    print('Running MD5 job')
    sfile = models.StoredFile.objects.select_related('servershare').get(pk=sf_id)
    fnpath = os.path.join(sfile.path, sfile.filename)
    res = tasks.get_md5.delay(sfile.id, fnpath, sfile.servershare.name)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')
    print('MD5 task queued')


def create_swestore_backup(job_id, sf_id, md5):
    print('Running swestore backup job')
    sfile = models.StoredFile.objects.get(pk=sf_id).select_related(
        'servershare')
    fnpath = os.path.join(sfile.path, sfile.filename),
    res = tasks.swestore_upload.delay(md5, sfile.servershare.name, fnpath,
                                      sfile.id)
    Task.objects.create(asyncid=res.id, job_id=job_id, state='PENDING')
    print('task queued')
