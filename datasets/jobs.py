import os
from itertools import cycle

from celery import states
from django.db.models import F
from django.urls import reverse
from celery import chain

from kantele import settings
from rawstatus.models import StoredFile
from datasets.models import Dataset, DatasetRawFile
from datasets import tasks
from rawstatus import tasks as filetasks
from jobs.post import save_task_chain, create_db_task


def move_dataset_storage_loc_getfiles(dset_id, src_path, dst_path):
    return StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=dset_id)


def move_dataset_storage_loc(job_id, dset_id, src_path, dst_path, *sf_ids):
    # within a server share
    print('Renaming dataset storage location job')
    t = tasks.rename_storage_location.delay(src_path, dst_path, sf_ids)
    create_db_task(t.id, job_id, src_path, dst_path, sf_ids)


def move_files_dataset_storage_getfiles(dset_id, dst_path, fn_ids):
    # Use both md5=sourcemd5 to avoid getting mzmls, other derived files
    # If files have not been transferred yet, then there is no storedfile..., or if it is not transferred correctly the MD5 is not done
    # So either: make that impossible
    # Or: reget the storedfiles on rerunning the job
    return StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id,
        rawfile__source_md5=F('md5'),
        rawfile_id__in=fn_ids)


def move_files_dataset_storage(job_id, dset_id, dst_path, rawfn_ids, *sf_ids):
    print('Moving dataset files to storage')
    new_sf_ids = StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dset_id,
        rawfile__source_md5=F('md5'),
        rawfile_id__in=rawfn_ids)
    if new_sf_ids.count() != len(sf_ids):
        print('Original job submission had {} stored files, but now there are {}'
              ' stored files'.format(len(sf_ids), new_sf_ids.count()))
    dset_files = StoredFile.objects.filter(pk__in=new_sf_ids, checked=True)
    # if only half of the files have been SCP arrived yet? Try more later:
    dset_registered_files = DatasetRawFile.objects.filter(
        dataset_id=dset_id, rawfile_id__in=rawfn_ids)
    if dset_files.count() != dset_registered_files.count():
        raise RuntimeError(
            'Not all files to move have been transferred or '
            'registered as transferred yet, or have non-matching MD5 sums '
            'between their registration and after transfer from input source. '
            'Holding this job and temporarily retrying it')
    for fn in dset_files:
        # TODO check for diff os.path.join(sevrershare, dst_path), not just
        # path?
        if fn.path != dst_path:
            tid = tasks.move_file_storage.delay(
                    fn.rawfile.name, fn.servershare.name, fn.path,
                    dst_path, fn.id).id
            create_db_task(tid, job_id, fn.rawfile.name, fn.servershare.name, fn.path, dst_path, fn.id)


def remove_files_from_dataset_storagepath_getfiles(dset_id, fn_ids):
    return StoredFile.objects.filter(rawfile_id__in=fn_ids)
        


def remove_files_from_dataset_storagepath(job_id, dset_id, fn_ids, *sf_ids):
    print('Moving files with ids {} from dataset storage to tmp, '
          'if not already there. Deleting if mzml'.format(fn_ids))
    for fn in StoredFile.objects.filter(pk__in=sf_ids).exclude(
            servershare__name=settings.TMPSHARENAME):
        if fn.filetype == 'mzml':
            fullpath = os.path.join(fn.path, fn.filename)
            tid = filetasks.delete_file.delay(fn.servershare.name, fullpath,
                                              fn.id).id
            create_db_task(tid, job_id, fn.servershare.name, fullpath, fn.id)
        else:
            tid = tasks.move_stored_file_tmp.delay(fn.rawfile.name, fn.path,
                                                   fn.id).id
            create_db_task(tid, job_id, fn.rawfile.name, fn.path, fn.id)


def get_mzmlconversion_taskchain(sfile, mzmlentry, storage_loc, queue, outqueue):
    return [
        tasks.convert_to_mzml.s(sfile.rawfile.name, sfile.path,
                                mzmlentry.filename, mzmlentry.id,
                                sfile.servershare.name,
                                reverse('jobs:createmzml'),
                                reverse('jobs:taskfail')).set(queue=queue),
        tasks.scp_storage.s(mzmlentry.id, storage_loc,
                            sfile.servershare.name, reverse('jobs:scpmzml'),
                            reverse('jobs:taskfail')).set(queue=outqueue),
        filetasks.get_md5.s(mzmlentry.id,
                            os.path.join(mzmlentry.path, mzmlentry.filename),
                            sfile.servershare.name)]


def get_or_create_mzmlentry(fn):
    try:
        mzsf = StoredFile.objects.get(rawfile_id=fn.rawfile_id,
                                      filetype='mzml')
    except StoredFile.DoesNotExist:
        mzmlfilename = os.path.splitext(fn.filename)[0] + '.mzML'
        mzsf = StoredFile(rawfile_id=fn.rawfile_id, filetype='mzml',
                          path=fn.rawfile.datasetrawfile.dataset.storage_loc,
                          servershare=fn.servershare,
                          filename=mzmlfilename, md5='', checked=False)
        mzsf.save()
    return mzsf


def convert_single_mzml(job_id, sf_id, queue=settings.QUEUES_PWIZ[0]):
    # FIXME may be this method can be moved to another module like rawstatus
    fn = StoredFile.objects.select_related(
        'servershare', 'rawfile__datasetrawfile__dataset').get(pk=sf_id)
    storageloc = fn.rawfile.datasetrawfile.dataset.storage_loc
    mzsf = get_or_create_mzmlentry(fn)
    if mzsf.checked:
        return
    runchain = get_mzmlconversion_taskchain(fn, mzsf, storageloc, queue,
                                            settings.QUEUES_PWIZOUT[queue])
    lastnode = chain(*runchain).delay()
    save_task_chain(lastnode, job_id)


def convert_dset_tomzml_getfiles(dset_id):
    for fn in StoredFile.objects.select_related(
            'servershare', 'rawfile__datasetrawfile__dataset').filter(
            rawfile__datasetrawfile__dataset_id=dset_id, filetype='raw'):
        mzsf = get_or_create_mzmlentry(fn)
        if mzsf.checked:
            continue
        yield fn


def convert_tomzml(job_id, dset_id, *sf_ids):
    """Multiple queues for this bc multiple boxes wo shared fs"""
    dset = Dataset.objects.get(pk=dset_id)
    queues = cycle(settings.QUEUES_PWIZ)
    for fn in StoredFile.objects.filter(
            pk__in=sf_ids, rawfile__datasetrawfile__dataset_id=dset_id).select_related(
            'servershare', 'rawfile__datasetrawfile__dataset'):
        mzsf = get_or_create_mzmlentry(fn)
        if mzsf.checked:
            continue
        queue = next(queues)
        outqueue = settings.QUEUES_PWIZOUT[queue]
        runchain = get_mzmlconversion_taskchain(fn, mzsf, dset.storage_loc, queue, outqueue)
        lastnode = chain(*runchain).delay()
        save_task_chain(lastnode, job_id)
