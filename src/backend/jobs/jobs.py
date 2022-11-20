import json
import requests
from celery import states
from django.utils import timezone
from urllib.parse import urljoin

from kantele import settings
from jobs.models import Job, Task
from rawstatus.models import StoredFile
from datasets import models as dm
from analysis import models as am


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
    
    def getfiles_query(self):
        pass

    def get_sf_ids_jobrunner(self, **kwargs):
        """This is run before running job, to define files used by
        the job (so it cant run if if files are in use by other job)"""
        return [x.pk for x in self.getfiles_query(**kwargs)]

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
    def getfiles_pre_query(self, **kwargs):
        return StoredFile.objects.filter(pk=kwargs['sf_id']).select_related(
                'servershare', 'rawfile')

    def getfiles_query(self, **kwargs):
        return self.getfiles_pre_query(**kwargs).get()

    def get_sf_ids_jobrunner(self, **kwargs):
        return [self.getfiles_query(**kwargs).id]


class DatasetJob(BaseJob):

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=kwargs['dset_id'])


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
