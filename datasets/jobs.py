from datetime import datetime

from rawstatus.models import StoredFile
from datasets.models import Dataset, DatasetRawFile
from datasets.tasks import move_file_storage, move_stored_file_tmp
from jobs.models import Job, Task, JobError


jobmap = {'move_file_storage': move_file_storage,
          'move_stored_file_tmp': move_stored_file_tmp,
          }


def create_job(name, jobtype):
    job = Job(function=name, jobtype=jobtype, timestamp=datetime.now(),
              state='processing')
    job.save()
    return job


def move_files_dataset_storage(dset_id, dst_path=False):
    print('Moving dataset files to storage')
    name = 'move_file_storage'
    dset_files = StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id).select_related(
        'rawfile__datasetrawfile')
    job = create_job(name, 'move')
    # FIXME what if only half of the files have been SCP arrived yet? Try more
    # later:
    dset_registered_files = DatasetRawFile.objects.filter(dataset_id=dset_id)
    if dset_files.count() != dset_registered_files.count():
        job.state = 'error'
        JobError.objects.create(
            job_id=job.id, message='Not all files have been transferred or '
            'registered as transferred yet. Holding this job and temporarily '
            'retrying it', autorequeue=True)
        job.save()
        return
    if not dst_path:
        dst_path = Dataset.objects.get(pk=dset_id).storage_loc
    task_ids = []
    for fn in dset_files:
        if fn.path != dst_path:
            task_ids.append(
                jobmap[name].delay(fn.rawfile.name, fn.servershare.name,
                                   fn.path, dst_path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job.id)
                              for tid in task_ids])


def remove_files_from_dataset_storagepath(fn_ids):
    name = 'move_stored_file_tmp'
    job = create_job(name, 'move')
    task_ids = []
    for fn in StoredFile.objects.filter(rawfile_id__in=fn_ids):
        task_ids.append(jobmap[name].delay(fn.rawfile.name, fn.path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job.id)
                              for tid in task_ids])
