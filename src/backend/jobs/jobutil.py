

from django.utils import timezone

from datasets import jobs as dsjobs
from rawstatus import jobs as rsjobs
from analysis import jobs as anjobs
from mstulos import jobs as mtjobs
from jobs.jobs import Jobstates
from jobs.models import Job


alljobs = [
        dsjobs.RenameDatasetStorageLoc,
        dsjobs.MoveFilesToStorage,
        dsjobs.MoveFilesStorageTmp,
        dsjobs.ConvertDatasetMzml,
        dsjobs.DeleteActiveDataset,
        dsjobs.DeleteDatasetMzml,
        dsjobs.BackupPDCDataset,
        dsjobs.ReactivateDeletedDataset,
        dsjobs.DeleteDatasetPDCBackup,
        dsjobs.RenameProject,
        dsjobs.MoveDatasetServershare,
        rsjobs.RsyncFileTransfer,
        rsjobs.CreatePDCArchive,
        rsjobs.RestoreFromPDC,
        rsjobs.RenameFile,
        rsjobs.MoveSingleFile,
        rsjobs.DeleteEmptyDirectory,
        rsjobs.PurgeFiles,
        rsjobs.DownloadPXProject,
        rsjobs.RegisterExternalFile,
        anjobs.RunLongitudinalQCWorkflow,
        anjobs.RunNextflowWorkflow,
        anjobs.RefineMzmls,
        anjobs.PurgeAnalysis,
        anjobs.DownloadFastaFromRepos,
        mtjobs.ProcessAnalysis,
        ]
jobmap = {job.refname: job for job in alljobs}



def check_job_error(name, **kwargs):
    jwrap = jobmap[name](False)
    return jwrap.check_error(**kwargs)


def create_job(name, state=False, **kwargs):
    '''Checks errors and then creates the job'''
    if not state:
        state = Jobstates.PENDING
    if error := check_job_error(name, **kwargs):
        jobdata = {'id': False, 'error': error}
    else:
        job = Job.objects.create(funcname=name, timestamp=timezone.now(),
            state=state, kwargs=kwargs)
        jobdata = {'id': job.id, 'error': False}
    return jobdata


def create_job_without_check(name, state=False, **kwargs):
    '''In case you do error checking before creating jobs, you can use this
    for quicker creation without another check'''
    if not state:
        state = Jobstates.PENDING
    job = Job.objects.create(funcname=name, timestamp=timezone.now(),
            state=state, kwargs=kwargs)
    return {'id': job.id, 'error': False}
