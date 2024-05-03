

from django.utils import timezone

from datasets import jobs as dsjobs
from rawstatus import jobs as rsjobs
from analysis import jobs as anjobs
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
        ]
jobmap = {job.refname: job for job in alljobs}


def create_job(name, state=False, **kwargs):
    if not state:
        state = Jobstates.PENDING
    jwrap = jobmap[name](False)
    if error := jwrap.check_error(**kwargs):
        jobdata = {'id': False, 'error': error}
    else:
        job = Job.objects.create(funcname=name, timestamp=timezone.now(),
            state=state, kwargs=kwargs)
        jobdata = {'id': job.id, 'error': False}
    return jobdata
