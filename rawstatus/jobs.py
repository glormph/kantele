import os
import requests
from urllib.parse import urlsplit
from datetime import datetime

from rawstatus import tasks, models
from datasets import tasks as dstasks
from kantele import settings
from jobs.jobs import BaseJob, SingleFileJob



class GetMD5(SingleFileJob):
    refname = 'get_md5'
    task = tasks.get_md5

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        fnpath = os.path.join(sfile.path, sfile.filename)
        self.run_tasks.append(((kwargs['source_md5'], sfile.id, fnpath, sfile.servershare.name), {}))


class CreatePDCArchive(SingleFileJob):
    refname = 'create_pdc_archive'
    task = tasks.pdc_archive

    def process(self, **kwargs):
        taskargs = upload_file_pdc_runtask(self.getfiles_query(**kwargs), isdir=kwargs['isdir'])
        if taskargs:
            self.run_tasks.append((taskargs, {}))
            print('PDC archival task queued')


class RestoreFromPDC(SingleFileJob):
    refname = 'restore_from_pdc_archive'
    task = tasks.pdc_restore

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        self.run_tasks.append((restore_file_pdc_runtask(sfile), {}))
        print('PDC archival task queued')


class UnzipRawFolder(SingleFileJob):
    refname = 'unzip_raw_datadir'
    task = tasks.unzip_folder

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        fnpath = os.path.join(sfile.path, sfile.filename)
        self.run_tasks.append(((sfile.servershare.name, fnpath, sfile.id), {}))
        print('Unzip task queued')


class RenameFile(SingleFileJob):
    refname = 'rename_file'
    task = dstasks.move_file_storage
    retryable = False
    """Only renames file inside same path/server. Does not move cross directories.
    This job checks if there is a RawFile entry with the same name in the same folder
    to avoid possible renaming collisions. Updates RawFile in job instead of view 
    since jobs are processed in a single queue.
    Since it only expects raw files it will also rename all mzML attached converted
    files. newname should NOT contain the file extension, only name.
    FIXME: make impossible to overwrite using move jobs at all (also moving etc)
    """

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        newname = kwargs['newname']
        fn_ext = os.path.splitext(sfile.filename)[1]
        if models.StoredFile.objects.exclude(pk=sfile.id).filter(
                rawfile__name=newname + fn_ext, path=sfile.path,
                servershare_id=sfile.servershare_id).exists():
            raise RuntimeError('A file in path {} with name {} already exists or will soon be created. Please choose another name'.format(sfile.path, newname))
        sfile.rawfile.name = newname + fn_ext
        sfile.rawfile.save()
        for changefn in sfile.rawfile.storedfile_set.select_related('mzmlfile'):
            oldname, ext = os.path.splitext(changefn.filename)
            special_type = '_refined' if hasattr(changefn, 'mzmlfile') and changefn.mzmlfile.refined else ''
            self.run_tasks.append(((
                changefn.filename, changefn.servershare.name,
                changefn.path, changefn.path, changefn.id),
                {'newname': '{}{}{}'.format(newname, special_type, ext)}))


class MoveSingleFile(SingleFileJob):
    refname = 'move_single_file'
    task = dstasks.move_file_storage

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        oldname = sfile.filename if not 'oldname' in kwargs or not kwargs['oldname'] else kwargs['oldname']
        taskkwargs = {x: kwargs[x] for x in ['newname'] if x in kwargs}
        self.run_tasks.append(((
            oldname, sfile.servershare.name,
            sfile.path, kwargs['dst_path'], sfile.id), taskkwargs))


class PurgeFiles(BaseJob):
    """Removes a number of files from active storage"""
    refname = 'purge_files'
    task = tasks.delete_file

    def getfiles_query(self, **kwargs):
        return models.StoredFile.objects.filter(pk__in=kwargs['sf_ids']).select_related('servershare')

    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs):
            fullpath = os.path.join(fn.path, fn.filename)
            self.run_tasks.append(((fn.servershare.name, fullpath, fn.id), {}))


class DeleteEmptyDirectory(BaseJob):
    """Check first if all the sfids are set to purged, indicating the dir is actually empty.
    Then queue a task. The sfids also make this job dependent on other jobs on those, as in
    the file-purging tasks before this directory deletion"""
    refname = 'delete_empty_directory'
    task = tasks.delete_empty_dir

    def getfiles_query(self, **kwargs):
        return models.StoredFile.objects.filter(pk__in=kwargs['sf_ids']).select_related(
                'servershare', 'rawfile')
    
    def process(self, **kwargs):
        sfiles = self.getfiles_query(**kwargs)
        if sfiles.count() and sfiles.count() == sfiles.filter(purged=True).count():
            fn = sfiles.last()
            self.run_tasks.append(((fn.servershare.name, fn.path), {}))
        elif not sfiles.count():
            pass
        else:
            raise RuntimeError('Cannot delete dir: according to the DB, there are still storedfiles which '
                'have not been purged yet in the directory')


class RegisterExternalFile(BaseJob):
    refname = 'register_external_raw'
    task = tasks.register_downloaded_external_raw
    """gets sf_ids, of non-checked downloaded external RAW files in tmp., checks MD5 and 
    registers to dataset
    """

    def getfiles_query(self, **kwargs):
        return models.StoredFile.objects.filter(rawfile_id__in=kwargs['rawfnids'], checked=False)
    
    def process(self, **kwargs):
        for fn in self.getfiles_query(**kwargs):
            self.run_tasks.append(((os.path.join(fn.path, fn.filename), fn.id,
                fn.rawfile_id, kwargs['sharename'], kwargs['dset_id']), {}))


class DownloadPXProject(BaseJob):
    refname = 'download_px_data'
    task = tasks.download_px_file_raw
    """gets sf_ids, of non-checked non-downloaded PX files.
    checks pride, fires tasks for files not yet downloaded. 
    """

    def getfiles_query(self, **kwargs):
        return models.StoredFile.objects.filter(rawfile_id__in=kwargs['rawfnids'], 
            checked=False).select_related('rawfile')
    
    def process(self, **kwargs):
        px_stored = {x.filename: x for x in self.getfiles_query(**kwargs)}
        for fn in call_proteomexchange(kwargs['pxacc']):
            ftpurl = urlsplit(fn['downloadLink'])
            filename = os.path.split(ftpurl.path)[1]
            if filename in px_stored and fn['fileSize'] == px_stored[filename].rawfile.size:
                pxsf = px_stored[filename]
                self.run_tasks.append(((
                    ftpurl.path, ftpurl.netloc, 
                    pxsf.id, pxsf.rawfile_id, 
                    fn['fileSize'], kwargs['sharename'], kwargs['dset_id']), {}))


def upload_file_pdc_runtask(sfile, isdir):
    """Generates the arguments for task to upload file to PDC. Reused in dataset jobs"""
    yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
    try:
        pdcfile = models.PDCBackedupFile.objects.get(storedfile=sfile, is_dir=isdir)
    except models.PDCBackedupFile.DoesNotExist:
        # only create entry when not already exists
        models.PDCBackedupFile.objects.create(storedfile=sfile, 
                pdcpath='', success=False)
    else:
        # Dont do more work than necessary, although this is probably too defensive
        if pdcfile.success and not pdcfile.deleted:
            return
    fnpath = os.path.join(sfile.path, sfile.filename)
    return (sfile.md5, yearmonth, sfile.servershare.name, fnpath, sfile.id, isdir)


def restore_file_pdc_runtask(sfile):
    backupfile = models.PDCBackedupFile.objects.get(storedfile=sfile)
    fnpath = os.path.join(sfile.path, sfile.filename)
    yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
    return (sfile.servershare.name, fnpath, backupfile.pdcpath, sfile.id, backupfile.is_dir)


def call_proteomexchange(pxacc):
    prideurl = 'https://www.ebi.ac.uk/pride/ws/archive/file/list/project/{}'.format(pxacc)
    return [x for x in requests.get(prideurl).json()['list'] if x['fileType'] == 'RAW']
