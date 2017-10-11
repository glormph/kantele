from datetime import datetime
import json

from jobs.models import Job
from datasets.models import DatasetJob
from rawstatus.models import FileJob
from datasets import jobs as dsjobs
from rawstatus import jobs as rsjobs


class Jobtypes(object):
    MOVE = 'move'
    CONVERT = 'convert'
    SEARCH = 'search'
    UPLOAD = 'upload'
    PROCESS = 'process'


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
          'create_swestore_backup':
          {'type': Jobtypes.UPLOAD, 'func': rsjobs.create_swestore_backup,
           'retry': False},
          'get_md5':
          {'type': Jobtypes.PROCESS, 'func': rsjobs.get_md5, 'retry': False},
          }


def create_file_job(name, sf_id, *args, **kwargs):
    """MD5, backup, etc"""
    jobargs = [sf_id] + list(args)
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=datetime.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    FileJob.objects.create(storedfile_id=sf_id, job_id=job.id)
    return job


def create_dataset_job(name, dset_id, *args, **kwargs):
    """Move, rename, search, convert"""
    jobargs = [dset_id] + list(args)
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=datetime.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    DatasetJob.objects.create(dataset_id=dset_id, job_id=job.id)
    return job
