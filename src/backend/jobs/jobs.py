import json
import requests
from celery import states
from django.utils import timezone
from urllib.parse import urljoin

from kantele import settings
from jobs.models import Job, Task
from rawstatus.models import StoredFile
from datasets import models as dm


class Jobstates:
    WAITING = 'wait'
    PENDING = 'pending'
    QUEUED = 'queued'
    PROCESSING = 'processing'
    ERROR = 'error'
    DONE = 'done'
    REVOKING = 'revoking'
    CANCELED = 'canceled'


JOBSTATES_WAIT = [Jobstates.WAITING, Jobstates.PENDING, Jobstates.QUEUED, Jobstates.PROCESSING]
JOBSTATES_DONE = [Jobstates.DONE, Jobstates.CANCELED]
JOBSTATES_PRE_OK_JOB = [Jobstates.WAITING, Jobstates.ERROR, Jobstates.REVOKING, Jobstates.CANCELED]


def create_job(name, state=False, **kwargs):
    if not state:
        state = Jobstates.PENDING
    job = Job(funcname=name, timestamp=timezone.now(),
            state=state, kwargs=kwargs)
    job.save()
    return job


class BaseJob:
    """Base class for jobs"""
    retryable = True
    revokable = False

    def __init__(self, job_id):
        self.job_id = job_id
        self.run_tasks = []
    
    def getfiles_query(self, **kwargs):
        return []

    def get_sf_ids_jobrunner(self, **kwargs):
        """This is run before running job, to define files used by
        the job (so it cant run if if files are in use by other job)"""
        return [x.pk for x in self.getfiles_query(**kwargs)]

    def get_dsids_jobrunner(self, **kwargs):
        return []

    def run(self, **kwargs):
        self.process(**kwargs)
        self.queue_tasks()

    def post(self):
        pass

    def queue_tasks(self):
        for task in self.run_tasks:
            args, kwargs = task[0], task[1]
            tid = self.task.delay(*args, **kwargs)
            self.create_db_task(tid, *args, **kwargs)
    
    def create_db_task(self, task_id, *args, **kwargs):
        t = Task(asyncid=task_id, job_id=self.job_id, state=states.PENDING, args=[args, kwargs])
        t.save()
        return t


class SingleFileJob(BaseJob):
    def getfiles_query(self, **kwargs):
        # FIXME do .get and .select_related in jobs itself?
        # As in multifile job (PurgeFiles)
        return StoredFile.objects.filter(pk=kwargs['sf_id']).select_related(
                'servershare', 'rawfile').get()

    def get_sf_ids_jobrunner(self, **kwargs):
        return [self.getfiles_query(**kwargs).id]

    def get_dsids_jobrunner(self, **kwargs):
        ''''In case a single file has a dataset'''
        return [x['pk'] for x in dm.Dataset.objects.filter(deleted=False, purged=False,
            datasetrawfile__rawfile__storedfile__id=kwargs['sf_id']).values('pk')]


class MultiFileJob(BaseJob):
    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(pk__in=kwargs['sf_ids'])

    def get_sf_ids_jobrunner(self, **kwargs):
        return [x['pk'] for x in self.getfiles_query(**kwargs).values('pk')]

    def get_dsids_jobrunner(self, **kwargs):
        ''''In case a single file has a dataset'''
        return [x['pk'] for x in dm.Dataset.objects.filter(deleted=False, purged=False,
            datasetrawfile__rawfile__storedfile__in=kwargs['sf_ids']).values('pk')]


class DatasetJob(BaseJob):
    '''Any job that changes a dataset (rename, adding/removing files, backup, reactivate)'''

    def get_dsids_jobrunner(self, **kwargs):
        return [kwargs['dset_id']]

    def get_sf_ids_jobrunner(self, **kwargs):
        '''Let all files associated with dataset wait, including added files on other path, and 
        removed files on dset path (will be moved to new folder before their move to tmp)'''
        dset = dm.Dataset.objects.get(pk=kwargs['dset_id'])
        dsfiles = StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=kwargs['dset_id'])
        ds_ondisk = StoredFile.objects.filter(servershare=dset.storageshare, path=dset.storage_loc)
        return [x.pk for x in dsfiles.union(ds_ondisk)]

    def getfiles_query(self, **kwargs):
        '''Get all files with same path as dset.storage_loc. This gets all files in the dset dir,
        not only the ones that have a datasetrawfile. This means there will also be
        ... FIXME which files are not dsetrawfile but still in the dataset dir?? Probably "removed files"
        or some other state in which files are not yet or no longer associated?
        '''
        dset = dm.Dataset.objects.get(pk=kwargs['dset_id'])
        return StoredFile.objects.filter(servershare=dset.storageshare, path=dset.storage_loc)


class ProjectJob(BaseJob):
    def get_dsids_jobrunner(self, **kwargs):
        return [x.pk for x in dm.Dataset.objects.filter(deleted=False, purged=False,
            runname__experiment__project_id=kwargs['proj_id'])]

    def getfiles_query(self, **kwargs):
        '''Get all files with same path as project_dsets.storage_locs, used to update
        path of those files post-job'''
        dsets = dm.Dataset.objects.filter(runname__experiment__project_id=kwargs['proj_id'])
        return StoredFile.objects.filter(
                servershare__in=[x.storageshare for x in dsets.distinct('storageshare')],
                path__in=[x.storage_loc for x in dsets.distinct('storage_loc')])

    def get_sf_ids_jobrunner(self, **kwargs):
        """Get all sf ids in project to mark them as not using pre-this-job"""
        projfiles = StoredFile.objects.filter(deleted=False, purged=False,
                rawfile__datasetrawfile__dataset__runname__experiment__project_id=kwargs['proj_id'])
        dsets = dm.Dataset.objects.filter(runname__experiment__project_id=kwargs['proj_id'])
        allfiles = StoredFile.objects.filter(servershare__in=[x.storageshare for x in dsets.distinct('storageshare')],
                path__in=[x.storage_loc for x in dsets.distinct('storage_loc')]).union(projfiles)
        return [x.pk for x in allfiles]


class MultiDatasetJob(BaseJob):

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id__in=kwargs['dset_ids'])


def check_existing_search_job(fname, wf_id, wfv_id, inputs, dset_ids, components, platenames=False, fractions=False, setnames=False):
    # FIXME this doesnt work, we have no args anymore in jobs, only kwargs!!
    # Also job fields are now JSON and cantbe searched with startswith
    return False

    jobargs = json.dumps([dset_ids])[:-1]  # leave out last bracket
    jobs = Job.objects.filter(funcname=fname, 
            args__startswith=jobargs).select_related('nextflowsearch')
    if platenames:
        extraargs = json.dumps([dset_ids] + [platenames] + [setnames])[:-1]  # leave out last bracket
        jobs = jobs.filter(args__startswith=extraargs)
    for job in jobs:
        job_is_duplicate = True
        storedargs = job.kwargs['inputs']
        nfs = job.nextflowsearch
        if nfs.workflow_id != wf_id or nfs.nfworkflow_id != wfv_id:
            continue
        for p in inputs['params']:
            if p not in storedargs['params']:
                job_is_duplicate = False
                break
        for flag, fnid in inputs['singlefiles'].items():
            try:
                if storedargs['singlefiles'][flag] != fnid:
                    job_is_duplicate = False
                    break
            except:
                job_is_duplicate = False
                break
        if job_is_duplicate:
            return job
    return False


def send_slack_message(text, channel):
    try:
        channelpath = settings.SLACK_HOOKS[channel.upper()]
    except KeyError:
        print('Kantele cant send slack message to channel {}, please check configuration'.format(channel))
        return
    url = urljoin(settings.SLACK_BASE, '/'.join([x for y in [settings.SLACK_WORKSPACE, channelpath] for x in y.split('/')]))
    req = requests.post(url, json={'text': text})
    # FIXME need to fix network outage (no raise_for_status
    try:
        req.raise_for_status()
    except Exception as error:
        print('Kantele cant send slack message to channel {}, please check configuration. Error was {}'.format(channel, error))
