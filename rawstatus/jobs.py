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
        self.run_tasks.append(((sfile.rawfile.source_md5, sfile.id, fnpath, sfile.servershare.name), {}))


class CreatePDCArchive(SingleFileJob):
    refname = 'create_pdc_archive'
    task = tasks.pdc_archive

    def process(self, **kwargs):
        self.upload_file_pdc(self.getfiles_query(**kwargs))

    def upload_file_pdc(self, sfile):
        """Possibly resuse this"""
        yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
        try:
            pdcfile = models.PDCBackedupFile.objects.get(storedfile=sfile)
        except models.PDCBackedupFile.DoesNotExist:
            # only create entry when not already exists
            models.PDCBackedupFile.objects.create(storedfile=sfile, 
                    pdcpath='', success=False)
        else:
            # Dont do more work than necessary, although this is probably too defensive
            if pdcfile.success and not pdcfile.deleted:
                return
        fnpath = os.path.join(sfile.path, sfile.filename)
        self.run_tasks.append(((sfile.md5, yearmonth, sfile.servershare.name, fnpath, sfile.id), {}))
        print('PDC archival task queued')


class RestoreFromPDC(SingleFileJob):
    refname = 'restore_from_pdc_archive'
    task = tasks.pdc_restore

    def process(self, **kwargs):
        backupfile = models.PDCBackedupFile.objects.get(storedfile_id=kwargs['sf_id'])
        sfile = self.getfiles_query(**kwargs)
        fnpath = os.path.join(sfile.path, sfile.filename)
        yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
        self.run_tasks.append(((sfile.md5, yearmonth, sfile.servershare.name, fnpath, sfile.id), {}))
        print('PDC archival task queued')


class UnzipRawFolder(SingleFileJob):
    refname = 'unzip_raw_folder'
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
                servershare_id=sfile.servershare_id).count():
            raise RuntimeError('A file in path {} with name {} already exists or will soon be created. Please choose another name'.format(sfile.path, newname))
        sfile.rawfile.name = newname + fn_ext
        sfile.rawfile.save()
        for changefn in sfile.rawfile.storedfile_set.all():
            oldname, ext = os.path.splitext(changefn.filename)
            special_type = '_refined' if changefn.filetype_id == settings.REFINEDMZML_SFGROUP_ID else ''
            self.run_tasks.append(((
                changefn.filename, changefn.servershare.name,
                changefn.path, changefn.path, changefn.id),
                {'newname': '{}{}{}'.format(newname, special_type, ext)}))


class MoveSingleFile(SingleFileJob):
    refname = 'move_single_file'
    task = dstasks.move_file_storage

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        oldname = sfile.filename if not kwargs['oldname'] else kwargs['oldname']
        taskkwargs = {x: kwargs[x] for x in ['newname', 'dstshare']}
        self.run_tasks.append(((
            oldname, sfile.servershare.name,
            sfile.path, kwargs['dst_path'], sfile.id), taskkwargs))


class DeleteEmptyDirectory(BaseJob):
    """Check first if all the sfids are set to purged, indicating the dir is actually empty.
    Then queue a task. The sfids also make this job dependent on other jobs on those, as in
    the file-purging tasks before this directory deletion"""
    refname = 'delete_empty_directory'
    task = tasks.delete_empty_dir

    def getfiles_query(self, **kwargs):
        return models.StoredFile.objects.filter(pk=kwargs['sf_ids']).select_related(
                'servershare', 'rawfile')
    
    def process(self, **kwargs):
        sfiles = self.getfiles_query(**kwargs)
        if sfiles.count() and sfiles.count() == sfiles.filter(purged=True).count():
            fn = sfiles.last()
            self.run_tasks.append(((fn.servershare.name, fn.path), {}))
        else:
            raise RuntimeError('Cannot delete dir: according to the DB, there are still storedfiles which '
                'have not been purged yet in the directory')


class DownloadPXProject(BaseJob):
    refname = 'download_px_data'
    task = tasks.download_px_file_raw
    """gets sf_ids, of non-checked non-downloaded PX files.
    checks pride, fires tasks for files not yet downloaded. 
    """

    def getfiles_query(self, rawfnids):
        return models.StoredFile.objects.filter(rawfile_id__in=rawfnids, 
            checked=False).select_related('rawfile')
    
    def process(self, **kwargs):
        px_stored = {x.filename: x for x in self.getfiles_query(kwargs['rawfnids'])}
        for fn in call_proteomexchange(kwargs['pxacc']):
            ftpurl = urlsplit(fn['downloadLink'])
            filename = os.path.split(ftpurl.path)[1]
            if filename in px_stored and fn['fileSize'] == px_stored[filename].rawfile.size:
                pxsf = px_stored[filename]
                self.run_tasks.append(((
                    ftpurl.path, ftpurl.netloc, 
                    pxsf.id, pxsf.rawfile_id, 
                    fn['fileSize'], kwargs['sharename'], kwargs['dset_id']), {}))


def call_proteomexchange(pxacc):
    prideurl = 'https://www.ebi.ac.uk/pride/ws/archive/file/list/project/{}'.format(pxacc)
    return [x for x in requests.get(prideurl).json()['list'] if x['fileType'] == 'RAW']
