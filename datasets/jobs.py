import os
from itertools import cycle

from django.db.models import F
from django.urls import reverse
from celery import chain

from kantele import settings
from rawstatus.models import StoredFile
from datasets.models import Dataset, DatasetRawFile
from datasets import tasks
from rawstatus import tasks as filetasks
from jobs.models import Task


def move_dataset_storage_loc(job_id, dset_id, src_path, dst_path):
    # within a server share
    print('Renaming dataset storage location job')
    storedfn_ids = [x.id for x in StoredFile.objects.select_related(
        'rawfile__datasetrawfile').filter(
        rawfile__datasetrawfile__dataset_id=dset_id)]
    t = tasks.rename_storage_location.delay(src_path, dst_path, storedfn_ids)
    Task.objects.create(asyncid=t.id, job_id=job_id, state='PENDING')


def move_files_dataset_storage(job_id, dset_id, fn_ids):
    print('Moving dataset files to storage')
    dset_files = StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id,
        rawfile__source_md5=F('md5'),
        rawfile_id__in=fn_ids).select_related('rawfile__datasetrawfile',
                                              'servershare')
    # if only half of the files have been SCP arrived yet? Try more later:
    dset_registered_files = DatasetRawFile.objects.filter(
        dataset_id=dset_id, rawfile_id__in=fn_ids)
    if dset_files.count() != dset_registered_files.count():
        raise RuntimeError(
            'Not all files to move have been transferred or '
            'registered as transferred yet, or have non-matching MD5 sums '
            'between their registration and after transfer from input source. '
            'Holding this job and temporarily retrying it')
    dst_path = Dataset.objects.get(pk=dset_id).storage_loc
    task_ids = []
    for fn in dset_files:
        # TODO check for diff os.path.join(sevrershare, dst_path), not just
        # path
        if fn.path != dst_path:
            task_ids.append(
                tasks.move_file_storage.delay(
                    fn.rawfile.name, fn.servershare.name, fn.path,
                    dst_path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id, state='PENDING')
                              for tid in task_ids])


def remove_files_from_dataset_storagepath(job_id, dset_id, fn_ids):
    print('Moving files with ids {} from dataset storage to tmp, '
          'if not already there. Deleting if mzml'.format(fn_ids))
    task_ids = []
    for fn in StoredFile.objects.filter(rawfile_id__in=fn_ids).exclude(
            servershare__name=settings.TMPSHARENAME):
        if fn.filetype == 'mzml':
            fullpath = os.path.join(fn.path, fn.filename)
            task_ids.append(filetasks.delete_file.delay(fn.servershare.name,
                                                        fullpath, fn.id))
        else:
            task_ids.append(tasks.move_stored_file_tmp.delay(fn.rawfile.name,
                                                             fn.path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id)
                              for tid in task_ids])


def convert_tomzml(job_id, dset_id):
    """Multiple queues for this bc multiple boxes wo shared fs"""
    dset = Dataset.objects.get(pk=dset_id)
    task_ids = []
    queues = cycle(settings.QUEUES_PWIZ)
    for fn in StoredFile.objects.select_related('servershare').filter(
            rawfile__datasetrawfile__dataset_id=dset_id, filetype='raw'):
        try:
            mzsf = StoredFile.objects.get(rawfile_id=fn.rawfile_id,
                                          filetype='mzml')
        except StoredFile.DoesNotExist:
            mzsf = StoredFile(rawfile_id=fn.rawfile_id, filetype='mzml',
                              path=fn.path, servershare=fn.servershare,
                              filename=fn.filename, md5='')
            mzsf.save()
        else:
            if mzsf.md5 != '':
                continue
        queue = next(queues)
        outqueue = settings.QUEUES_PWIZOUT[queue]
        runchain = [
            tasks.convert_to_mzml.s(fn.rawfile.name, fn.path,
                                    fn.servershare.name,
                                    reverse('jobs:taskfail')).set(queue=queue),
            tasks.scp_storage.s(mzsf.id, dset.storage_loc, fn.servershare.name,
                                reverse('files:createmzml'),
                                reverse('jobs:taskfail')).set(queue=outqueue)
                    ]
        task_ids.append(chain(*runchain).delay().id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id)
                              for tid in task_ids])
