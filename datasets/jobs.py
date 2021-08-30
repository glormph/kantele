import os
from itertools import cycle

from django.db.models import F
from django.urls import reverse
from celery import chain

from kantele import settings
from rawstatus.models import StoredFile, ServerShare, StoredFileType
from datasets.models import Dataset, DatasetRawFile
from analysis.models import Proteowizard, MzmlFile, NextflowWfVersion
from datasets import tasks
from rawstatus import tasks as filetasks
from jobs.models import TaskChain
from jobs.jobs import BaseJob, DatasetJob, create_job
# FIXME backup jobs need doing
from rawstatus import jobs as rsjobs


class RenameDatasetStorageLoc(DatasetJob):
    refname = 'rename_dset_storage_loc'
    task = tasks.rename_dset_storage_location
    retryable = False

    def process(self, **kwargs):
        """Fetch fresh storage_loc src dir here, then queue for move from there"""
        dset = Dataset.objects.get(pk=kwargs['dset_id'])
        if dset.storage_loc != kwargs['dstpath']:
            self.run_tasks = [((dset.storage_loc, kwargs['dstpath'], kwargs['dset_id'], [x.id for x in self.getfiles_query(**kwargs)]), {})]


class MoveFilesToStorage(DatasetJob):
    refname = 'move_files_storage'
    task = tasks.move_file_storage

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
        dstpath = Dataset.objects.get(pk=kwargs['dset_id']).storage_loc
        for fn in dset_files:
            # TODO check for diff os.path.join(sevrershare, dst_path), not just
            # path? Only relevant in case of cross-share moves.
            if fn.path != dstpath:
                self.run_tasks.append(
                        ((fn.rawfile.name, fn.servershare.name, fn.path, dstpath, fn.id), {})
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
        for fn in self.getfiles_query(**kwargs).select_related('mzmlfile'):
            if hasattr(fn, 'mzmlfile'):
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
    task = tasks.run_convert_mzml_nf
    """Note that this job also runs the windows tasks in case the older
    pwiz version is run"""

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(
            rawfile__datasetrawfile__dataset_id=kwargs['dset_id']).exclude(
            mzmlfile__isnull=False).select_related(
            'servershare', 'rawfile__datasetrawfile__dataset')

    def process(self, **kwargs):
        dset = Dataset.objects.get(pk=kwargs['dset_id'])
        pwiz = Proteowizard.objects.get(pk=kwargs['pwiz_id'])
        res_share = ServerShare.objects.get(name=settings.ANALYSISSHARENAME).id if pwiz.is_docker else False
        # First create jobs to delete old files
        # TODO problem may arise if eg storage worker is down and hasnt finished processing the
        # and old batch of files. Then the new files will come in before the worker is restarted.
        # The old files, which will at that point be lying around in their inbox: 
        # analysis/mzml_in folder, will then be 1.moved, 2.deleted, 3. new file move job will error
        delete_sfids = []
        for fn in StoredFile.objects.filter(rawfile__datasetrawfile__dataset=kwargs['dset_id'],
                deleted=False, purged=False, checked=True, 
                mzmlfile__isnull=False).exclude(mzmlfile__pwiz=pwiz).values('id'):
            delete_sfids.append(fn['id'])
        if len(delete_sfids):
            print('Queueing {} old mzML files for deletion before creating '
            'new files'.format(len(delete_sfids)))
            create_job('purge_files', sf_ids=delete_sfids)
        nf_raws, win_mzmls = [], []
        for fn in self.getfiles_query(**kwargs):
            mzsf = get_or_create_mzmlentry(fn, pwiz=pwiz, servershare_id=res_share)
            if mzsf.checked and not mzsf.purged:
                continue
            # refresh file status for previously purged (deleted from disk)  mzmls 
            if mzsf.purged:
                mzsf.checked = False
                mzsf.purged = False
            mzsf.servershare_id = res_share if pwiz.is_docker else mzsf.servershare_id
            mzsf.save()
            nf_raws.append((fn.servershare.name, fn.path, fn.filename, mzsf.id))
            win_mzmls.append((fn, mzsf))
        if pwiz.is_docker and len(nf_raws):
            print('Queuing {} raw files for conversion'.format(len(nf_raws)))
            nfwf = NextflowWfVersion.objects.select_related('nfworkflow').get(
                    pk=pwiz.nf_version_id)
            run = {'timestamp': kwargs['timestamp'],
                   'dset_id': dset.id,
                   'wf_commit': nfwf.commit,
                   'nxf_wf_fn': nfwf.filename,
                   'repo': nfwf.nfworkflow.repo,
                   }
            params = ['--container', pwiz.container_version]
            for pname in ['options', 'filters']:
                p2parse = kwargs.get(pname, [])
                if len(p2parse):
                    params.extend(['--{}'.format(pname), ';'.join(p2parse)])
            self.run_tasks.append(((run, params, nf_raws), {'pwiz_id': pwiz.id}))
        elif not pwiz.is_docker and len(win_mzmls):
            options = ['--{}'.format(x) for x in kwargs.get('options', [])]
            filters = [y for x in kwargs.get('filters', []) for y in ['--filter', x]]
            queues = cycle(settings.QUEUES_PWIZ)
            for fn, mzsf in win_mzmls:
                queue = next(queues)
                outqueue = settings.QUEUES_PWIZOUT[queue]
                self.run_tasks.append(((fn, mzsf, dset.storage_loc, options + filters, queue, outqueue), {}))
    
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
        if len(self.run_tasks):
            pwiz_v = self.run_tasks[0][1].get('pwiz_id', '-1')
            if Proteowizard.objects.filter(pk=pwiz_v, is_docker=True).exists():
                # checks if dockerized-NF workflow should be queued
                super().queue_tasks()
            else:
                # if not docker/NF -- run on windows box
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
        pwiz = Proteowizard.objects.get(pk=kwargs['pwiz_id'])
        mzsf = get_or_create_mzmlentry(fn, pwiz=pwiz)
        if mzsf.servershare_id != fn.servershare_id:
            # change servershare, in case of bugs the raw sf is set to tmp servershare
            # then after it wont be changed when rerunning the job
            mzsf.servershare_id = fn.servershare_id
            mzsf.save()
        if mzsf.checked:
            pass
        else:
            options = ['--{}'.format(x) for x in kwargs.get('options', [])]
            filters = [y for x in kwargs.get('filters', []) for y in ['--filter', x]]
            self.run_tasks.append(((fn, mzsf, storageloc, options + filters, queue, settings.QUEUES_PWIZOUT[queue]), {}))


class DeleteDatasetMzml(DatasetJob):
    """Removes dataset from active storage"""
    refname = 'delete_mzmls_dataset'
    task = filetasks.delete_file

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs).filter(deleted=False, purged=False, checked=True, mzmlfile__isnull=False):
            fullpath = os.path.join(fn.path, fn.filename)
            print('Queueing deletion of mzML file {} from dataset {}'.format(fullpath, kwargs['dset_id']))
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}))


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
        for sfile in self.getfiles_query(**kwargs).exclude(mzmlfile__isnull=False).exclude(pdcbackedupfile__success=True, pdcbackedupfile__deleted=False):
            isdir = hasattr(sfile.rawfile.producer, 'msinstrument') and sfile.filetype.is_folder
            self.run_tasks.append((rsjobs.upload_file_pdc_runtask(sfile, isdir=isdir), {}))


class ReactivateDeletedDataset(DatasetJob):
    refname = 'reactivate_dataset'
    task = filetasks.pdc_restore

    def process(self, **kwargs):
        for sfile in self.getfiles_query(**kwargs).exclude(mzmlfile__isnull=False).filter(purged=True, pdcbackedupfile__isnull=False):
            self.run_tasks.append((rsjobs.restore_file_pdc_runtask(sfile), {}))
        # Also set archived/archivable files which are already active (purged=False) to not deleted in UI
        self.getfiles_query(**kwargs).filter(purged=False, deleted=True, pdcbackedupfile__isnull=False).update(deleted=False)


class DeleteDatasetPDCBackup(BaseJob):
    refname = 'delete_dataset_coldstorage'
    # TODO
    # should be agnostic of files in PDC, eg if no files found, loop length is zero
    # this for e.g empty or active-only dsets


def get_or_create_mzmlentry(fn, pwiz, refined=False, servershare_id=False):
    if not servershare_id:
        servershare_id = fn.servershare_id
    try:
        mzsf = StoredFile.objects.select_related('mzmlfile').get(rawfile_id=fn.rawfile_id, 
                mzmlfile__isnull=False, mzmlfile__pwiz=pwiz, mzmlfile__refined=refined)
    except StoredFile.DoesNotExist:
        mzmlfilename = os.path.splitext(fn.filename)[0] + '.mzML'
        mzsf = StoredFile.objects.create(rawfile_id=fn.rawfile_id, filetype_id=fn.filetype_id,
                          path=fn.rawfile.datasetrawfile.dataset.storage_loc,
                          servershare_id=servershare_id,
                          filename=mzmlfilename, md5='', checked=False)
        mzml = MzmlFile.objects.create(sfile=mzsf, pwiz=pwiz, refined=refined)
    else:
        mzml = mzsf.mzmlfile
    return mzsf
