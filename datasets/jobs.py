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
from jobs.models import TaskChain
from jobs.jobs import BaseJob, DatasetJob
# FIXME backup jobs need doing
from rawstatus import jobs as rsjobs


class RenameDatasetStorageLoc(DatasetJob):
    refname = 'rename_storage_loc'
    task = tasks.rename_storage_location
    retryable = False
    #print('Renaming dataset storage location job')

    def process(self, **kwargs):
        """Just passthrough of arguments to task"""
        self.run_tasks = [((kwargs['srcpath'], kwargs['dstpath'], [self.getfiles_query(**kwargs)]), {})]


class MoveFilesToStorage(DatasetJob):
    refname = 'move_files_storage'
    task = tasks.move_file_storage
    #print('Moving dataset files to storage')

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(
            rawfile__datasetrawfile__dataset_id=kwargs['dset_id'],
            rawfile__source_md5=F('md5'),
            rawfile_id__in=kwargs['rawfn_ids'],
            checked=True)

    def process(self, **kwargs):
        dset_files = self.getfiles_query(**kwargs)
        # if only half of the files have been SCP arrived yet? Try more later:
        dset_registered_files = DatasetRawFile.objects.filter(
            dataset_id=kwargs['dset_id'], rawfile_id__in=kwargs['rawfn_ids'])
        if dset_files.count() != dset_registered_files.count():
            raise RuntimeError(
                'Not all files to move have been transferred or '
                'registered as transferred yet, or have non-matching MD5 sums '
                'between their registration and after transfer from input source. '
                'Holding this job, you may retry it when files have arrived')
        for fn in dset_files:
            # TODO check for diff os.path.join(sevrershare, dst_path), not just
            # path?
            if fn.path != kwargs['dst_path']:
                self.run_tasks.append(
                        ((fn.rawfile.name, fn.servershare.name, fn.path, kwargs['dst_path'], fn.id), {})
                        )


class MoveFilesStorageTmp(BaseJob):
    """Moves file from a dataset back to a tmp/inbox-like share"""
    refname = 'move_stored_files_tmp'
    task = False
    #print('Moving files with ids {} from dataset storage to tmp, '
    #      'if not already there. Deleting if mzml'.format(fn_ids))

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.select_related('filetype').filter(
            rawfile_id__in=kwargs['fn_ids']).exclude(servershare__name=settings.TMPSHARENAME)

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs):
            if fn.filetype.filetype == 'mzml':
                fullpath = os.path.join(fn.path, fn.filename)
                self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}, filetasks.delete_file))
            else:
                self.run_tasks.append(((fn.filename, fn.path, fn.id), {}, tasks.move_stored_file_tmp))

    def queue_tasks(self):
        for task in self.run_tasks:
            args, kwargs, taskfun = task[0], task[1], task[2]
            tid = taskfun.delay(*args, **kwargs)
            self.create_db_task(tid, self.job_id, *args, **kwargs)


class ConvertDatasetMzml(BaseJob):
    refname = 'convert_dataset_mzml'

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(
            rawfile__datasetrawfile__dataset_id=kwargs['dset_id'],
            filetype_id=settings.RAW_SFGROUP_ID).select_related(
            'servershare', 'rawfile__datasetrawfile__dataset')

    def process(self, **kwargs):
        dset = Dataset.objects.get(pk=kwargs['dset_id'])
        queues = cycle(settings.QUEUES_PWIZ)
        filtopts = kwargs.get('options', []) + [y for x in kwargs.get('filters', []) for y in ['--filter', x]]
        for fn in self.getfiles_query(**kwargs):
            mzsf = get_or_create_mzmlentry(fn, settings.MZML_SFGROUP_ID)
            if mzsf.checked and not mzsf.purged:
                continue
            # refresh file status for previously purged (deleted from disk)  mzmls 
            if mzsf.purged:
                mzsf.checked = False
                mzsf.purged = False
                mzsf.save()
            queue = next(queues)
            outqueue = settings.QUEUES_PWIZOUT[queue]
            self.run_tasks.append(((fn, mzsf, dset.storage_loc, filtopts, queue, outqueue), {}))
    
    def get_mzmlconversion_taskchain(self, sfile, mzmlentry, storage_loc, filtopts, queue, outqueue):
        args = [[sfile.rawfile.name, sfile.path, mzmlentry.filename, mzmlentry.id,
                 sfile.servershare.name, filtopts, reverse('jobs:createmzml'),
                 reverse('jobs:taskfail')],
                [mzmlentry.id, storage_loc, sfile.servershare.name,
                 reverse('jobs:scpmzml'), reverse('jobs:taskfail')],
                [mzmlentry.id, os.path.join(mzmlentry.path, mzmlentry.filename),
                 sfile.servershare.name]]
        return args, [tasks.convert_to_mzml.s(*args[0]).set(queue=queue),
                tasks.scp_storage.s(*args[1]).set(queue=outqueue),
                filetasks.get_md5.s(*args[2])]

    def save_task_chain(self, taskchain, args):
        chain_ids = []
        while taskchain.parent:
            chain_ids.append(taskchain.id)
            taskchain = taskchain.parent
        chain_ids.append(taskchain.id)
        for chain_id, arglist in zip(chain_ids, args):
            t = self.create_db_task(chain_id, self.job_id, *arglist)
            TaskChain.objects.create(task_id=t.id, lasttask=chain_ids[0])

    def queue_tasks(self):
        for task in self.run_tasks:
            args, kwargs = task[0], task[1]
            alltaskargs, runchain = self.get_mzmlconversion_taskchain(*args)
            lastnode = chain(*runchain).delay()
            self.save_task_chain(lastnode, alltaskargs)


class ConvertFileMzml(ConvertDatasetMzml):
    refname = 'convert_single_mzml'

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.select_related('rawfile__datasetrawfile__dataset').filter(pk=kwargs['sf_id'])

    def process(self, **kwargs):
        queue = kwargs.get('queue', settings.QUEUES_PWIZ[0])
        fn = self.getfiles_query(**kwargs).get()
        storageloc = fn.rawfile.datasetrawfile.dataset.storage_loc
        mzsf = get_or_create_mzmlentry(fn, settings.MZML_SFGROUP_ID)
        filtopts = kwargs.get('options', []) + [y for x in kwargs.get('filters', []) for y in ['--filter', x]]
        if mzsf.servershare_id != fn.servershare_id:
            # change servershare, in case of bugs the raw sf is set to tmp servershare
            # then after it wont be changed when rerunning the job
            mzsf.servershare_id = fn.servershare_id
            mzsf.save()
        if mzsf.checked:
            pass
        else:
            self.run_tasks.append(((fn, mzsf, storageloc, filtopts, queue, settings.QUEUES_PWIZOUT[queue]), {}))


class DeleteActiveDataset(DatasetJob):
    """Removes dataset from active storage"""
    refname = 'delete_active_dataset'
    task = filetasks.delete_file

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs):
            fullpath = os.path.join(fn.path, fn.filename)
            print('Purging {} from dataset {}'.format(fullpath, kwargs['dset_id']))
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}))


class BackupPDCDataset(DatasetJob):
    """Transfers all raw files in dataset to backup"""
    refname = 'backup_dataset'
    task = filetasks.pdc_archive
    
    def process(self, **kwargs):
        for sfile in self.getfiles_query(**kwargs).exclude(filetype_id__in=settings.SECONDARY_FTYPES).exclude(pdcbackedupfile__success=True, pdcbackedupfile__deleted=False):
            self.run_tasks.append((rsjobs.upload_file_pdc_runtask(sfile), {}))


class ReactivateDeletedDataset(DatasetJob):
    refname = 'reactivate_dataset'
    task = filetasks.pdc_restore

    def process(self, **kwargs):
        for sfile in self.getfiles_query(**kwargs).exclude(filetype_id__in=settings.SECONDARY_FTYPES).filter(purged=True, pdcbackedupfile__isnull=False):
            self.run_tasks.append((rsjobs.restore_file_pdc_runtask(sfile), {}))
        # Also set archived/archivable files which are already active (purged=False) to not deleted in UI
        self.getfiles_query(**kwargs).filter(purged=False, deleted=True, pdcbackedupfile__isnull=False).update(deleted=False)


class DeleteDatasetPDCBackup(BaseJob):
    refname = 'delete_dataset_coldstorage'
    # TODO
    # should be agnostic of files in PDC, eg if no files found, loop length is zero
    # this for e.g empty or active-only dsets


def get_or_create_mzmlentry(fn, group_id, servershare_id=False):
    if not servershare_id:
        servershare_id = fn.servershare_id
    try:
        mzsf = StoredFile.objects.get(rawfile_id=fn.rawfile_id,
                                      filetype_id=group_id)
    except StoredFile.DoesNotExist:
        mzmlfilename = os.path.splitext(fn.filename)[0] + '.mzML'
        mzsf = StoredFile(rawfile_id=fn.rawfile_id, filetype_id=group_id,
                          path=fn.rawfile.datasetrawfile.dataset.storage_loc,
                          servershare_id=servershare_id,
                          filename=mzmlfilename, md5='', checked=False)
        mzsf.save()
    return mzsf
