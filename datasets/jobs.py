from rawstatus.models import StoredFile
from datasets.models import Dataset, DatasetRawFile
from datasets import tasks
from jobs.models import Task


def move_dataset_storage_loc(job_id, dset_id, src_path, dst_path):
    # within a server share
    print('Renaming dataset storage location job')
    storedfn_ids = StoredFile.objects.select_related(
        'rawfile__datasetrawfile').filter(
        rawfile__datasetrawfile__dataset_id=dset_id)
    t = tasks.rename_storage_location.delay(src_path, dst_path, storedfn_ids)
    Task.objects.create(asyncid=t.id, job_id=job_id, state='PENDING')


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
    print('Moving files with ids {} from dataset to tmp'.format(fn_ids))
    task_ids = []
    for fn in StoredFile.objects.filter(rawfile_id__in=fn_ids):
        task_ids.append(tasks.move_stored_file_tmp.delay(fn.rawfile.name,
                                                         fn.path, fn.id).id)
    Task.objects.bulk_create([Task(asyncid=tid, job_id=job_id)
                              for tid in task_ids])
