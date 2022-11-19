import os
import requests
from urllib.parse import urlsplit, urlparse, urljoin
import ftplib
from datetime import datetime

from rawstatus import tasks, models
from datasets import tasks as dstasks
from kantele import settings
from jobs.jobs import BaseJob, SingleFileJob


def create_upload_dst_web(rfid, ftype):
    '''To create path for uploaded files'''
    return os.path.join(settings.TMP_UPLOADPATH, f'{rfid}.{ftype}')

def get_host_upload_dst(web_dst):
    '''To get path for uploaded files on the host (not the container)'''
    return web_dst.replace(settings.TMP_UPLOADPATH, settings.HOST_UPLOADDIR, 1)


class RsyncFileTransfer(SingleFileJob):
    refname = 'rsync_transfer'
    task = tasks.rsync_transfer_file

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        dstpath = os.path.join(sfile.path, sfile.filename)
        self.run_tasks.append(((sfile.id, get_host_upload_dst(kwargs['src_path']),
            dstpath, sfile.servershare.name, sfile.filetype.is_folder,
            sfile.filetype.stablefiles), {}))


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
        print('PDC restore task queued')


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
                changefn.path, changefn.path, changefn.id, changefn.servershare.name),
                {'newname': '{}{}{}'.format(newname, special_type, ext)}))


class MoveSingleFile(SingleFileJob):
    refname = 'move_single_file'
    task = dstasks.move_file_storage

    def process(self, **kwargs):
        sfile = self.getfiles_query(**kwargs)
        oldname = sfile.filename if not 'oldname' in kwargs or not kwargs['oldname'] else kwargs['oldname']
        taskkwargs = {x: kwargs[x] for x in ['newname'] if x in kwargs}
        dstsharename = kwargs.get('dstsharename') or sfile.servershare.name
        self.run_tasks.append(((
            oldname, sfile.servershare.name,
            sfile.path, kwargs['dst_path'], sfile.id, dstsharename), taskkwargs))


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
        return models.StoredFile.objects.filter(rawfile_id__in=kwargs['shasums'], 
            checked=False).select_related('rawfile')
    
    def process(self, **kwargs):
        px_stored = {x.filename: x for x in self.getfiles_query(**kwargs)}
        for fn in call_proteomexchange(kwargs['pxacc']):
            ftpurl = urlsplit(fn['downloadLink'])
            filename = os.path.split(ftpurl.path)[1]
            if filename in px_stored and fn['fileSize'] == px_stored[filename].rawfile.size:
                # Only download non-checked (i.e. non-confirmed already downloaded) files
                pxsf = px_stored[filename]
                self.run_tasks.append(((
                    ftpurl.path, ftpurl.netloc, 
                    pxsf.id, pxsf.rawfile_id, fn['sha1sum'],
                    fn['fileSize'], kwargs['sharename'], kwargs['dset_id']), {}))


def upload_file_pdc_runtask(sfile, isdir):
    """Generates the arguments for task to upload file to PDC. Reused in dataset jobs"""
    yearmonth = datetime.strftime(sfile.regdate, '%Y%m')
    try:
        pdcfile = models.PDCBackedupFile.objects.get(storedfile=sfile, is_dir=isdir)
    except models.PDCBackedupFile.DoesNotExist:
        # only create entry when not already exists
        models.PDCBackedupFile.objects.create(storedfile=sfile, is_dir=isdir,
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
    # FIXME check SHA1SUM when getting this
    accessions = {'expfn': 'PRIDE:0000584',
            'ftp': 'PRIDE:0000469',
            'raw': 'PRIDE:0000404',
    }
    inst_type_map = {
        'MS:1001742': 'velos', # LTQ Orbitrap Velos 
        #'MS:1001909': 'velos', # Velos plus
        'MS:1001910': 'velos', # Orbitrap Elite
        'MS:1002835': 'velos', # Orbitrap Classic
        'MS:1001911': 'qe',  # Q Exactive
        'MS:1002523': 'qe',  # Q Exactive HF
        'MS:1002634': 'qe',  # Q Exactive plus
        'MS:1002877': 'qe',  # Q Exactive HF-X
        'MS:1002732': 'lumos',  # Orbitrap Fusion Lumos
# FIXME more instruments
# FIXME if we are trying to download OUR OWN data, we get problem with MD5 already existing
# ALso when re-queueing this job, there is a problem when MD5 is identical
# Possibly solve with "this is our data, please reactivate from PDC"
    }
    prideurl = 'https://www.ebi.ac.uk/pride/ws/archive/v2/'
    # Get project instruments before files so we can assign instrument types to the files
    project = requests.get(urljoin(prideurl, 'projects/{}'.format(pxacc)))
    if project.status_code != 200:
        raise RuntimeError(f'Connected to ProteomeXchange but could not get project information, '
                'status code {project.status_code}')
    try:
        all_inst = project.json()['instruments']
    except KeyError:
        raise RuntimeError('Could not determine instruments from ProteomeXchange project "{pxacc}"')
    try:
        inst_types = {x['accession']: inst_type_map[x['accession']] for x in all_inst}
    except KeyError:
        fail_inst = ', '.join([x['accession'] for x in all_inst if x['accession'] not in inst_type_map])
        raise RuntimeError(f'Not familiar with instrument type(s) {fail_inst}, please ask admin to upgrade Kantele')
    amount_instruments = len(set(inst_types.values()))

    # Now try to fetch the experiment design file if needed
    allfiles = requests.get(urljoin(prideurl, 'files/byProject'), params={'accession': pxacc}).json()
    fn_instr_map = {}
    for fn in allfiles:
        # first get experiment design file, if it exists
        if fn['fileCategory']['accession'] == accessions['expfn']:
            try:
                ftpfn = [x for x in fn['publicFileLocations'] if x['accession'] == accessions['ftp']][0]['value']
            except (KeyError, IndexError):
                if amount_instruments > 1:
                    raise RuntimeError('Cannot get FTP location for experiment design file')
                else:
                    print('Skipping experiment design file, cannot find it in file listing')
            expfn = urlparse(ftpfn)
            explines = []
            try:
                ftp = ftplib.FTP(expfn.netloc)
                ftp.login()
                ftp.retrlines(f'RETR {expfn.path}', lambda x: explines.append(x.strip().split('\t')))
            except ftplib.all_errors as ftperr:
                if amount_instruments > 1:
                    raise RuntimeError(f'Could not download experiment design file {ftpfn}')
                else:
                    print(f'Skipping experiment design file {ftpfn}, errored upon downloading')
            else:
                instr_ix = explines[0].index('comment[instrument]')
                fn_ix = explines[0].index('comment[data file]')
                for line in explines[1:]:
                    # parse e.g. "AC=MS:1002526;NT=Q Exactive Plus"
                    instr_acc = [x.split('=')[1] for x in line[instr_ix].split(';') if x[:2] == 'AC'][0]
                    fn_instr_map[line[fn_ix]] = inst_type_map[instr_acc]
            break
    if not fn_instr_map:
        print('Could not find experiment design file')
 
    fetchable_files = []
    first_instrument = set(inst_types.values()).pop()
    for fn in allfiles:
        try:
            ftype = fn['fileCategory']['accession']
            shasum = fn['checksum']
            dlink = [x for x in fn['publicFileLocations'] if x['accession'] == accessions['ftp']][0]['value']
            filesize = fn['fileSizeBytes']
            filename = fn['fileName']
        except (KeyError, IndexError):
            raise RuntimeError('Could not get download information for a file from ProteomeXchange')
        if ftype == accessions['raw']:
            if filename in fn_instr_map:
                instr_type = fn_instr_map[filename]
            elif amount_instruments == 1:
                instr_type = first_instrument
            else:
                raise RuntimeError(f'Could not find instrument for file {filename} and '
                        'more than 1 instrument type used in project')
            fetchable_files.append({'fileSize': filesize, 'downloadLink': dlink,
                'sha1sum': shasum, 'instr_type': instr_type})
    return fetchable_files
