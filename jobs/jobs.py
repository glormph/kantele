import json
from celery import states
from django.utils import timezone

from jobs.models import Job, Task
from rawstatus.models import FileJob, StoredFile
from datasets import models as dm
from analysis import models as am


class Jobstates:
    PENDING = 'pending'
    PROCESSING = 'processing'
    ERROR = 'error'
    DONE = 'done'
    CANCELED = 'canceled'
    WAITING = 'wait'


JOBSTATES_WAIT = [Jobstates.WAITING, Jobstates.PENDING, Jobstates.PROCESSING]
JOBSTATES_DONE = [Jobstates.DONE, Jobstates.CANCELED]
JOBSTATES_PREJOB = [Jobstates.WAITING, Jobstates.PENDING]


def create_job(name, **kwargs):
    job = Job(funcname=name, timestamp=timezone.now(),
              state=Jobstates.PENDING, kwargs=json.dumps(kwargs))
    job.save()
    return job


class BaseJob:
    """Base class for jobs"""
    retryable = True

    def __init__(self, job_id):
        self.job_id = job_id
        self.run_tasks = []
    
    def getfiles_query(self):
        pass

    def get_sf_ids(self, **kwargs):
        """This is set before running job, and when discovering job by runner to estimate
        if the job can be run yet (if files are in use by other job)"""
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
        strargs = json.dumps([args, kwargs])
        t = Task(asyncid=task_id, job_id=self.job_id, state=states.PENDING, args=strargs)
        t.save()
        return t


class SingleFileJob(BaseJob):
    def getfiles_pre_query(self, **kwargs):
        return StoredFile.objects.filter(pk=kwargs['sf_id']).select_related(
                'servershare', 'rawfile')

    def getfiles_query(self, **kwargs):
        return self.getfiles_pre_query(**kwargs).get()

    def get_sf_ids(self, **kwargs):
        return [self.getfiles_query(**kwargs).id]


class DatasetJob(BaseJob):

    def getfiles_query(self, **kwargs):
        return StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=kwargs['dset_id'])


class MultiDatasetJob(BaseJob):

    def getfiles_query(self, **kwargs):
         return StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id__in=kwargs['dset_ids'])


def check_existing_search_job(fname, wf_id, wfv_id, inputs, dset_ids, platenames=False, fractions=False, setnames=False):
    jobargs = json.dumps([dset_ids])[:-1]  # leave out last bracket
    jobs = Job.objects.filter(funcname=fname, 
            args__startswith=jobargs).select_related('nextflowsearch')
    if platenames:
        extraargs = json.dumps([dset_ids] + [platenames] + [setnames])[:-1]  # leave out last bracket
        jobs = jobs.filter(args__startswith=extraargs)
    for job in jobs:
        job_is_duplicate = True
        storedargs = json.loads(job.kwargs)['inputs']
        #storedargs = [x for x in json.loads(job.args) if type(x)==dict and 'params' in x][0]
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
