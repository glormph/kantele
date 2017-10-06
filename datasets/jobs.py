from rawstatus.models import StoredFile
from datasets.models import Dataset, DatasetRawFile
from datasets import tasks
from jobs.models import Task


def move_files_dataset_storage(job_id, dset_id, fn_ids):
    print('Moving dataset files to storage')
    dset_files = StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id,
        rawfile_id__in=fn_ids).select_related('rawfile__datasetrawfile',
                                              'servershare')
    # if only half of the files have been SCP arrived yet? Try more later:
    dset_registered_files = DatasetRawFile.objects.filter(
        dataset_id=dset_id, rawfile_id__in=fn_ids)
    if dset_files.count() != dset_registered_files.count():
        raise RuntimeError(
            'Not all files to move have been transferred or '
            'registered as transferred yet. Holding this job and temporarily '
            'retrying it')
    dst_path = Dataset.objects.get(pk=dset_id).storage_loc
    task_ids = []
    for fn in dset_files:
        if fn.path != dst_path:
            task_ids.append(
                tasks.move_file_storage.delay(
                    fn.rawfile.name, fn.servershare.name, fn.path,
                    dst_path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id, state='PENDING')
                              for tid in task_ids])


def remove_files_from_dataset_storagepath(job_id, dset_id, fn_ids):
    #name = 'move_stored_file_tmp'
    #job = jobutil.create_dataset_job(name, 'move', dset_id)
    print('Moving files with ids {} from dataset to tmp'.format(fn_ids))
    task_ids = []
    for fn in StoredFile.objects.filter(rawfile_id__in=fn_ids):
        task_ids.append(tasks.move_stored_file_tmp.delay(fn.rawfile.name,
                                                         fn.path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id)
                              for tid in task_ids])


jobmap = {'move_files_storage':
          {'func': move_files_dataset_storage, 'retry': True},
          'move_stored_files_tmp':
          {'func': remove_files_from_dataset_storagepath, 'retry': False},
          'rename_storage_loc':
          {'func': move_dataset_storage_loc, 'retry': False},
          }
