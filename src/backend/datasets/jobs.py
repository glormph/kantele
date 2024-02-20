import os

from django.db.models import F
from django.urls import reverse

from kantele import settings
from rawstatus.models import StoredFile, ServerShare, StoredFileType
from datasets.models import Dataset, DatasetRawFile, Project
from analysis.models import Proteowizard, MzmlFile, NextflowWfVersionParamset
from datasets import tasks
from rawstatus import tasks as filetasks
from jobs.jobs import BaseJob, DatasetJob, create_job
from rawstatus import jobs as rsjobs


class RenameProject(BaseJob):
    '''Uses task that does os.rename on project lvl dir. Needs also to update
    dsets / storedfiles to new path post job'''
    refname = 'rename_top_lvl_projectdir'
    task = tasks.rename_top_level_project_storage_dir
    retryable = False

    def getfiles_query(self, **kwargs):
        '''Get all files with same path as project_dsets.storage_locs, used to update
        path of those files post-job'''
        dsets = Dataset.objects.filter(runname__experiment__project_id=kwargs['proj_id'])
        return StoredFile.objects.filter(
                servershare__in=[x.storageshare for x in dsets.distinct('storageshare')],
                path__in=[x.storage_loc for x in dsets.distinct('storage_loc')])

    def get_sf_ids_jobrunner(self, **kwargs):
        """Get all sf ids in project to mark them as not using pre-this-job"""
        projfiles = StoredFile.objects.filter(
                rawfile__datasetrawfile__dataset__runname__experiment__project_id=kwargs['proj_id'])
        dsets = Dataset.objects.filter(runname__experiment__project_id=kwargs['proj_id'])
        allfiles = StoredFile.objects.filter(servershare__in=[x.storageshare for x in dsets.distinct('storageshare')],
                path__in=[x.storage_loc for x in dsets.distinct('storage_loc')]).union(projfiles)
        return [x.pk for x in allfiles]

    def process(self, **kwargs):
        """Fetch fresh project name here, then queue for move from there"""
        new_is_oldname = True
        for ds in Dataset.objects.select_related('storageshare').filter(
                runname__experiment__project_id=kwargs['proj_id']):
            ds_toploc = ds.storage_loc.split(os.path.sep)[0]
            ssharename = ds.storageshare.name
            if ds_toploc != kwargs['newname']:
                new_is_oldname = False
                break
        if not new_is_oldname:
            self.run_tasks = [((ssharename, ds_toploc, kwargs['newname'], kwargs['proj_id'],
                [x.id for x in self.getfiles_query(**kwargs)]), {})]


class RenameDatasetStorageLoc(DatasetJob):
    '''Renames dataset, then updates storage_loc of it and path of all dataset storedfiles
    which have same path as dataset.storage_loc, including any deleted files, but not newly
    added files from tmp'''
    refname = 'rename_dset_storage_loc'
    task = tasks.rename_dset_storage_location
    retryable = False

    def process(self, **kwargs):
        """Fetch fresh storage_loc src dir here, then queue for move from there"""
        dset = Dataset.objects.get(pk=kwargs['dset_id'])
        if dset.storage_loc != kwargs['dstpath']:
            self.run_tasks = [((dset.storageshare.name, dset.storage_loc, kwargs['dstpath'],
                kwargs['dset_id'], [x.id for x in self.getfiles_query(**kwargs)]), {})]


class MoveDatasetServershare(DatasetJob):
    '''Moves all files associated to a dataset to another servershare'''
    refname = 'move_dset_servershare'
    task = tasks.rsync_dset_servershare

    def process(self, **kwargs):
        dset = Dataset.objects.values('storage_loc').get(pk=kwargs['dset_id'])
        sfs = self.getfiles_query(**kwargs).values('path', 'servershare__name', 'filename', 'pk')
        rsync_sf = sfs.filter(deleted=False, purged=False, checked=True)
        paths = sfs.distinct('path')
        if paths.count() > 1:
            raise RuntimeError('Dataset live files are spread over multiple paths and cannot '
                    f'be consolidated to {kwargs["dstsharename"]} under one path. '
                    f'Please group files first, to dset storage location {dset.storage_loc}')
        if paths.get()['path'] != dset['storage_loc']:
            raise RuntimeError('Dataset storage location is different from paths of dset live files, '
                    f'Please make sure files are in correct location, {dset.storage_loc}')
        sharename = sfs.first()['servershare__name']
        if sharename == kwargs['dstsharename']:
            raise RuntimeError('Cannot move dataset to same share as its files are on using this job')
        self.run_tasks.append(((kwargs['dset_id'], sharename, dset['storage_loc'],
            kwargs['dstsharename'], [x['filename'] for x in rsync_sf], [x['pk'] for x in sfs]), {}))


class MoveFilesToStorage(DatasetJob):
    refname = 'move_files_storage'
    task = tasks.move_file_storage

    def getfiles_query(self, **kwargs):
        '''Get all files going to dataset (passed ids), but only those with 
        identical md5 as registered raw file (i.e. no mzMLs)'''
        ds_files = StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=kwargs['dset_id'])
        return ds_files.filter(rawfile__source_md5=F('md5'), rawfile_id__in=kwargs['rawfn_ids'],
                checked=True)

    def process(self, **kwargs):
        dset_files = self.getfiles_query(**kwargs)
        # if only half of the files have arrived on tmp yet? Try more later:
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
                        ((fn.rawfile.name, fn.servershare.name, fn.path, dstpath, 
                            fn.id, settings.PRIMARY_STORAGESHARENAME), {})
                        )


class MoveFilesStorageTmp(DatasetJob):
    """Moves file from a dataset back to a tmp/inbox-like share"""
    refname = 'move_stored_files_tmp'
    task = False

    def getfiles_query(self, **kwargs):
        '''Select all files which are in dataset path, but not the purged ones, and
        filter out passed rawfiles'''
        return super().getfiles_query(**kwargs).select_related('filetype').filter(purged=False,
            rawfile_id__in=kwargs['fn_ids'])

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs).select_related('mzmlfile', 'servershare'):
            if hasattr(fn, 'mzmlfile'):
                fullpath = os.path.join(fn.path, fn.filename)
                self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}, filetasks.delete_file))
            else:
                self.run_tasks.append(((fn.servershare.name, fn.filename, fn.path, fn.id), {}, tasks.move_stored_file_tmp))

    def queue_tasks(self):
        for task in self.run_tasks:
            args, kwargs, taskfun = task[0], task[1], task[2]
            tid = taskfun.delay(*args, **kwargs)
            self.create_db_task(tid, self.job_id, *args, **kwargs)


class ConvertDatasetMzml(DatasetJob):
    refname = 'convert_dataset_mzml'
    task = tasks.run_convert_mzml_nf
    revokable = True

    def getfiles_query(self, **kwargs):
        '''Return raw files only (from dset path)'''
        return super().getfiles_query(**kwargs).exclude(mzmlfile__isnull=False).select_related(
                'servershare', 'rawfile__datasetrawfile__dataset', 'filetype')

    def process(self, **kwargs):
        dset = Dataset.objects.get(pk=kwargs['dset_id'])
        pwiz = Proteowizard.objects.get(pk=kwargs['pwiz_id'])
        res_share = ServerShare.objects.get(pk=kwargs['dstshare_id'])
        # First create jobs to delete old files
        # TODO problem may arise if eg storage worker is down and hasnt finished processing the
        # and old batch of files. Then the new files will come in before the worker is restarted.
        # The old files, which will at that point be lying around in their inbox: 
        # analysis/mzml_in folder, will then be 1.moved, 2.deleted, 3. new file move job will error
        nf_raws = []
        for fn in self.getfiles_query(**kwargs):
            mzsf = get_or_create_mzmlentry(fn, pwiz=pwiz, servershare_id=res_share.pk)
            if mzsf.checked and not mzsf.purged:
                continue
            # refresh file status for previously purged (deleted from disk)  mzmls,
            # set servershare in case it is not analysis
            if mzsf.purged:
                mzsf.checked = False
                mzsf.purged = False
            mzsf.servershare = res_share
            mzsf.save()
            nf_raws.append((fn.servershare.name, fn.path, fn.filename, mzsf.id))
        if not nf_raws:
            return
        # FIXME last file filetype decides mzml input filetype, we should enforce
        # same filetype files in a dataset if possible
        ftype = mzsf.filetype.name
        print('Queuing {} raw files for conversion'.format(len(nf_raws)))
        nfwf = NextflowWfVersionParamset.objects.select_related('nfworkflow').get(
                pk=pwiz.nf_version_id)
        run = {'timestamp': kwargs['timestamp'],
               'dset_id': dset.id,
               'wf_commit': nfwf.commit,
               'nxf_wf_fn': nfwf.filename,
               'repo': nfwf.nfworkflow.repo,
               'nfrundirname': 'small' if len(nf_raws) < 500 else 'larger',
               'dstsharename': res_share.name,
               'runname': f'{dset.id}_convert_mzml_{kwargs["timestamp"]}',
               }
        params = ['--container', pwiz.container_version]
        for pname in ['options', 'filters']:
            p2parse = kwargs.get(pname, [])
            if len(p2parse):
                params.extend(['--{}'.format(pname), ';'.join(p2parse)])
        profiles = ','.join(nfwf.profiles)
        self.run_tasks.append(((run, params, nf_raws, ftype, nfwf.nfversion, profiles), {'pwiz_id': pwiz.id}))


class ConvertFileMzml(ConvertDatasetMzml):
    # FIXME deprecate, no longer using this
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
    """Removes dataset mzml files from active storage"""
    refname = 'delete_mzmls_dataset'
    task = filetasks.delete_file

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs).filter(deleted=False, purged=False, checked=True,
                mzmlfile__pwiz_id=kwargs['pwiz_id']):
            fullpath = os.path.join(fn.path, fn.filename)
            print('Queueing deletion of mzML file {fullpath} from dataset {kwargs["dset_id"]}')
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}))


class DeleteActiveDataset(DatasetJob):
    """Removes dataset from active storage"""
    refname = 'delete_active_dataset'
    # FIXME need to be able to delete directories
    task = filetasks.delete_file

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs).select_related('filetype').filter(purged=False):
            fullpath = os.path.join(fn.path, fn.filename)
            print('Purging {} from dataset {}'.format(fullpath, kwargs['dset_id']))
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id, fn.filetype.is_folder), {}))


class BackupPDCDataset(DatasetJob):
    """Transfers all raw files in dataset to backup"""
    refname = 'backup_dataset'
    task = filetasks.pdc_archive
    
    def process(self, **kwargs):
        for sfile in self.getfiles_query(**kwargs).exclude(mzmlfile__isnull=False).exclude(
                pdcbackedupfile__success=True, pdcbackedupfile__deleted=False).filter(
                        rawfile__datasetrawfile__dataset_id=kwargs['dset_id']):
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


class DeleteDatasetPDCBackup(DatasetJob):
    refname = 'delete_dataset_coldstorage'
    # TODO this job is not ready
    # should be agnostic of files in PDC, eg if no files found, loop length is zero
    # this for e.g empty or active-only dsets


def get_or_create_mzmlentry(fn, pwiz, refined=False, servershare_id=False):
    '''This also resets the path of the mzML file'''
    if not servershare_id:
        servershare_id = fn.servershare_id
    mzmlfilename = os.path.splitext(fn.filename)[0] + '.mzML'
    mzsf, cr = StoredFile.objects.update_or_create(mzmlfile__pwiz=pwiz, mzmlfile__refined=refined,
            rawfile_id=fn.rawfile_id, filetype_id=fn.filetype_id, defaults={
                'md5': f'mzml_{fn.rawfile.source_md5[5:]}', 'servershare_id': servershare_id,
                'filename': mzmlfilename, 'path': fn.rawfile.datasetrawfile.dataset.storage_loc})
    if cr:
        MzmlFile.objects.create(sfile=mzsf, pwiz=pwiz, refined=refined)
    return mzsf
