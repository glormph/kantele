from datetime import datetime
import json

from jobs.models import Job
from datasets.models import DatasetJob


class Jobtypes(object):
    MOVE = 'move'
    CONVERT = 'convert'
    SEARCH = 'search'
    FTP = 'ftp'


class Jobstates(object):
    PENDING = 'pending'
    PROCESSING = 'processing'
    ERROR = 'error'
    DONE = 'done'


def create_dataset_job(name, jobtype, dset_id, *args, **kwargs):
    jobargs = [dset_id] + list(args)
    job = Job(funcname=name, jobtype=jobtype, timestamp=datetime.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    DatasetJob.objects.create(dataset_id=dset_id, job_id=job.id)
    return job
