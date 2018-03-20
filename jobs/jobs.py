from datetime import datetime
import json
from celery import states

from jobs.models import Job, Task
from rawstatus.models import FileJob
from datasets import jobs as dsjobs
from rawstatus import jobs as rsjobs
from analysis import jobs as anjobs


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


"""Jobmap contains all jobs in system by name. The retry field indicates a
job is retryable, which means the job should be side-effect free, i.e. possible
to retry without messing things up.
"""
jobmap = {'move_files_storage':
          {'type': Jobtypes.MOVE, 'func': dsjobs.move_files_dataset_storage,
           'getfns': dsjobs.move_files_dataset_storage_getfiles, 'retry': True},
          'move_single_file':
          {'type': Jobtypes.MOVE, 'func': rsjobs.move_single_file,
           'retry': True},
          'move_stored_files_tmp':
          {'type': Jobtypes.MOVE, 'retry': True,
           'func': dsjobs.remove_files_from_dataset_storagepath,
           'getfns': dsjobs.remove_files_from_dataset_storagepath_getfiles},
          'rename_storage_loc':
          {'type': Jobtypes.MOVE, 'func': dsjobs.move_dataset_storage_loc,
           'getfns': dsjobs.move_dataset_storage_loc_getfiles, 'retry': False},
          'convert_dataset_mzml':
          {'type': Jobtypes.MOVE, 'func': dsjobs.convert_tomzml,
           'getfns': dsjobs.convert_dset_tomzml_getfiles, 'retry': True},
          'convert_single_mzml':
          {'type': Jobtypes.MOVE, 'func': dsjobs.convert_single_mzml,
           'retry': True},
          'create_swestore_backup':
          {'type': Jobtypes.UPLOAD, 'func': rsjobs.create_swestore_backup,
           'retry': True},
          'get_md5':
          {'type': Jobtypes.PROCESS, 'func': rsjobs.get_md5, 'retry': True},
          'run_longit_qc_workflow':
          {'type': Jobtypes.PROCESS, 'func': anjobs.auto_run_qc_workflow,
           'retry': True},
          'run_ipaw_nextflow':
          {'type': Jobtypes.PROCESS, 'func': anjobs.run_ipaw,
           'getfns': anjobs.run_ipaw_getfiles, 'retry': True},
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
    prejob_args = [dset_id] + list(args)
    sf_ids = [x.id for x in jobmap[name]['getfns'](*prejob_args)]
    jobargs = prejob_args + sf_ids
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=datetime.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    FileJob.objects.bulk_create([FileJob(storedfile_id=sf_id, job_id=job.id) for sf_id in sf_ids])
    return job


def is_job_retryable(job, tasks=False):
    if job.funcname in jobmap and jobmap[job.funcname]['retry'] and is_job_ready(job):
        return True
    return False


def is_job_ready(job=False, tasks=False):
    if tasks is False:
        tasks = Task.objects.filter(job_id=job.id)
    if {t.state for t in tasks}.difference(states.READY_STATES):
        return False
    return True
