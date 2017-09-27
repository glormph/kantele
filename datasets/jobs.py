from datetime import datetime

from rawstatus.models import StoredFile
from datasets.models import Dataset
from jobs.models import Job, Task


def move_files_dataset_storage(dset_id, dst_path=False):
    job = Job(function=move_tmpfile_storage, type='move',
              timestamp=datetime.now())
    job.save()
    dset_files = StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id).select_related(
        'rawfile__datasetrawfile')
    if not dst_path:
        dst_path = Dataset.objects.get(pk=dset_id)
    task_ids = []
    for fn in dset_files:
        if fn.path != dst_path:
            task_ids.append(
                move_tmpfile_storage.delay(fn.rawfile.name, fn.path, fn.id,
                                           dst_path).id)
    Task.objects.bulk_create([Task(async_id=tid, job_id=job.id)
                              for tid in task_ids])


def remove_files_from_dataset_storagepath(fn_ids):
    job = Job(function=move_stored_file_tmp, type='move',
              timestamp=datetime.now())
    job.save()
    task_ids = []
    for fn in StoredFile.objects.filter(rawfile_id__in=fn_ids):
        task_ids.append(move_stored_file_tmp.delay(fn.rawfile.name, fn.path,
                                                   fn.id).id)
    Task.objects.bulk_create([Task(async_id=tid, job_id=job.id)
                              for tid in task_ids])


import os
import shutil
import app
import config


@app.shared_task
def move_file_storage(fn, srcshare, srcpath, dstpath, fn_id):
    src = os.path.join(
        {'storage': config.STORAGESHARE, 'tmp': config.TMPSHARE}[srcshare],
        srcpath, fn)
    dst = os.path.join(config.STORAGESHARE, dstpath, fn)
    shutil.move(src, dst)
    # FIXME API call to add  new path to StoredFile in DB, OR MV BACK
    ok = True
    if not ok:
        shutil.move(dst, src)
        return  # FIXME ERROR for celery


@app.shared_task
def move_stored_file_tmp(fn, path, fn_id):
    src = os.path.join(config.STORAGESHARE, path, fn)
    dst = os.path.join(config.TMPSHARE, fn)
    shutil.move(src, dst)
    # FIXME API call to add new path to db, MV BACK IF HTTP NOT 200
    ok = True
    if not ok:
        shutil.move(dst, src)
        return  # FIXME ERROR for celery
