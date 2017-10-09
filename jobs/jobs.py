from datetime import datetime
import json

from jobs.models import Job
from datasets.models import DatasetJob
from datasets import jobs as dsjobs


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


jobmap = {'move_files_storage':
          {'type': Jobtypes.MOVE, 'func': dsjobs.move_files_dataset_storage,
           'retry': True},
          'move_stored_files_tmp':
          {'type': Jobtypes.MOVE, 'retry': False,
           'func': dsjobs.remove_files_from_dataset_storagepath},
          'rename_storage_loc':
          {'type': Jobtypes.MOVE, 'func': dsjobs.move_dataset_storage_loc,
           'retry': False},
          }


def create_dataset_job(name, dset_id, *args, **kwargs):
    jobargs = [dset_id] + list(args)
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=datetime.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    DatasetJob.objects.create(dataset_id=dset_id, job_id=job.id)
    return job
