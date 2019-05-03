from datetime import datetime
import json
from celery import states
from django.utils import timezone

from jobs.models import Job, Task
from rawstatus.models import FileJob
from datasets import jobs as dsjobs
from datasets import models as dm
from rawstatus import jobs as rsjobs
from analysis import jobs as anjobs
from analysis import models as am


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
    CANCELED = 'canceled'
    WAITING = 'wait'


JOBSTATES_WAIT = [Jobstates.WAITING, Jobstates.PENDING, Jobstates.PROCESSING]
JOBSTATES_DONE = [Jobstates.DONE, Jobstates.CANCELED]
JOBSTATES_PREJOB = [Jobstates.WAITING, Jobstates.PENDING]

"""Jobmap contains all jobs in system by name. The retry field indicates a
job is retryable, which means the job should be side-effect free, i.e. possible
to retry without messing things up.
"""
# FIXME implement this as decorator for jobs: @job ? how to do with getfns?
jobmap = {'move_files_storage':
          {'type': Jobtypes.MOVE, 'func': dsjobs.move_files_dataset_storage,
           'getfns': dsjobs.move_files_dataset_storage_getfiles, 'retry': True},
          'move_single_file':
          {'type': Jobtypes.MOVE, 'func': rsjobs.move_single_file,
           'retry': True},
          'rename_file':
          {'type': Jobtypes.MOVE, 'func': rsjobs.rename_file,
           'retry': False},
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
          'create_pdc_archive':
          {'type': Jobtypes.UPLOAD, 'func': rsjobs.create_pdc_archive,
           'retry': True},
          'create_swestore_backup':
          {'type': Jobtypes.UPLOAD, 'func': rsjobs.create_swestore_backup,
           'retry': True},
          'get_md5':
          {'type': Jobtypes.PROCESS, 'func': rsjobs.get_md5, 'retry': True},
          'download_px_data':
          {'type': Jobtypes.UPLOAD, 'retry': True,
           'func': rsjobs.download_px_project,
           'getfns': rsjobs.download_px_project_getfiles},
          'run_longit_qc_workflow':
          {'type': Jobtypes.PROCESS, 'func': anjobs.auto_run_qc_workflow,
           'retry': True},
          'run_ipaw_nextflow':
          {'type': Jobtypes.PROCESS, 'func': anjobs.run_nextflow,
           'getfns': anjobs.run_nextflow_getfiles, 'retry': True},
          'refine_mzmls':
          {'type': Jobtypes.PROCESS, 'func': anjobs.refine_mzmls,
           'getfns': anjobs.refine_mzmls_getfiles, 'retry': True},
          'purge_analysis':
          {'func': anjobs.purge_analysis, 'type': Jobtypes.MOVE,
           'getfns': anjobs.purge_analysis_getfiles, 'retry': True},
          'delete_analysis_directory':
          {'func': rsjobs.delete_empty_directory, 'type': Jobtypes.MOVE,
           'getfns': anjobs.purge_analysis_getfiles, 'retry': True},
          }


def create_file_job(name, sf_id, *args, **kwargs):
    """MD5, backup, etc"""
    jobargs = [sf_id] + list(args)
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=timezone.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    FileJob.objects.create(storedfile_id=sf_id, job_id=job.id)
    return job


def create_dataset_job(name, dset_id, *args, **kwargs):
    """Move, rename, search, convert"""
    prejob_args = [dset_id] + list(args)
    return store_ds_job(name, prejob_args, **kwargs)


def store_ds_job(name, prejob_args, **kwargs):
    pjres = jobmap[name]['getfns'](*prejob_args)
    sf_ids = [x.id for x in pjres]
    jobargs = prejob_args + sf_ids
    job = Job(funcname=name, jobtype=jobmap[name]['type'],
              timestamp=timezone.now(),
              state=Jobstates.PENDING, args=json.dumps(jobargs),
              kwargs=json.dumps(kwargs))
    job.save()
    FileJob.objects.bulk_create([FileJob(storedfile_id=sf_id, job_id=job.id) for sf_id in sf_ids])
    return job


def check_existing_search_job(fname, dset_ids, strips, fractions, setnames, wfid, wfvid, params):
    jobargs = json.dumps([dset_ids] + [strips] + [setnames])[:-1]  # leave out last bracket
    for job in Job.objects.filter(funcname=fname, jobtype=jobmap[fname]['type'],
            args__startswith=jobargs).select_related('nextflowsearch'):
        job_is_duplicate = True
        storedargs = json.loads(job.args)[6]
        nfs = job.nextflowsearch
        if nfs.workflow_id != wfid or nfs.nfworkflow_id != wfvid:
            continue
        for p in params['params']:
            if p not in storedargs['params']:
                job_is_duplicate = False
                break
        for flag, fnid in params['singlefiles'].items():
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


def is_job_retryable_ready(job, tasks=False):
    return is_job_retryable(job) and is_job_ready(job)


def is_job_retryable(job, tasks=False):
    return job.funcname in jobmap and jobmap[job.funcname]['retry']


def is_job_ready(job=False, tasks=False):
    if tasks is False:
        tasks = Task.objects.filter(job_id=job.id)
    if {t.state for t in tasks}.difference(states.READY_STATES):
        return False
    return True


def get_job_analysis(job):
    try:
        analysis = job.nextflowsearch.analysis
    except am.NextflowSearch.DoesNotExist:
        analysis = False 
    return analysis


def get_job_ownership(job, request):
    """returns {'ownertype': user/admin, 'usernames': [], 'owner_loggedin': T/F}
    """
    owner_loggedin = False
    ownertype = 'user'
    ana = get_job_analysis(job)
    if ana:
        usernames = [ana.user.username]
        owner_loggedin = request.user.id == ana.user.id
    else:
        fjs = job.filejob_set.select_related('storedfile__rawfile__datasetrawfile__dataset')
        try:
            users = list({y.user for x in fjs for y in x.storedfile.rawfile.datasetrawfile.dataset.datasetowner_set.all()})
        except dm.DatasetRawFile.DoesNotExist:
            usernames = list({x.storedfile.rawfile.producer.name for x in fjs})
            ownertype = 'admin'
        else:
            usernames = [x.username for x in users]
            owner_loggedin = request.user.id in [x.id for x in users]
    return {'usernames': usernames, 'owner_loggedin': owner_loggedin, 'type': ownertype,
             'is_staff': request.user.is_staff}
