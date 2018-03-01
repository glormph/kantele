"""
These tasks are to be run by the celery beat automatic task runner every 10 seconds or so.
It contains a very simple job scheduler. The more advanced job scheduling is to be done by
celery chains etc, Nextflow, or Galaxy or whatever one likes.

The scheduling here includes:

file jobs (jobs executed on an existing file)
dataset jobs (jobs executed on a part of or a full dataset)

Dataset jobs that are of type MOVE will wait for other dataset jobs of that type, same for file jobs.
Jobs that are of another type (PROCESS, UPLOAD), will wait for MOVE jobs (also only 
inside its job or dataset jobclass)

This makes it hard to mix dataset and file jobs in a chain but please use a nicer framework for that.
The job scheduler here is only to make sure that multiple jobs clicked by the user wait
for eachother.
"""

import json

from celery import shared_task, states

from kantele import settings
from jobs.models import Task, Job, JobError, TaskChain
from jobs.jobs import Jobstates, Jobtypes, jobmap
from datasets.models import DatasetJob
from rawstatus.models import FileJob


@shared_task
def run_ready_jobs():
    print('Checking job queue')
    job_ds_map, active_move_dsets, active_dsets = collect_dsjob_activity()
    job_fn_map, active_move_files, active_files = collect_filejob_activity()
    print('{} jobs in queue, including errored jobs'.format(len(job_ds_map) +
                                                            len(job_fn_map)))
    for job in Job.objects.order_by('timestamp').exclude(
            state__in=[Jobstates.DONE]):
        jobdsets = job_ds_map[job.id] if job.id in job_ds_map else set()
        jobfiles = job_fn_map[job.id] if job.id in job_fn_map else set()
        print('Job {}, state {}, type {}'.format(job.id, job.state, job.jobtype))
        if job.state == Jobstates.ERROR:
            print('ERRROR MESSAGES:')
            for joberror in JobError.objects.filter(job_id=job.id):
                print(joberror.message)
            print('END error messages')
        elif job.state == Jobstates.PROCESSING:
            tasks = Task.objects.filter(job_id=job.id)
            print('Updating task status for active job {} - {}'.format(job.id, job.funcname))
            process_job_tasks(job, tasks)
        elif job.state == Jobstates.PENDING and job.jobtype == Jobtypes.MOVE:
            print('Found new move job {} - {}'.format(job.id, job.funcname))
            # do not start move job if there is activity on dset or files
            if (active_files.intersection(jobfiles) or
                    active_dsets.intersection(jobdsets)):
                print('Deferring move job since datasets {} or files {} are '
                      'being used in '
                      'other job'.format(active_dsets.intersection(jobdsets),
                                         active_files.intersection(jobfiles)))
                continue
            else:
                print('Executing move job {}'.format(job.id))
                if job.id in job_ds_map:
                    [active_dsets.add(ds) for ds in job_ds_map[job.id]]
                    [active_move_dsets.add(ds) for ds in job_ds_map[job.id]]
                if job.id in job_fn_map:
                    [active_files.add(fn) for fn in job_fn_map[job.id]]
                    [active_move_files.add(fn) for fn in job_fn_map[job.id]]
                run_job(job, jobmap)
        elif job.state == Jobstates.PENDING:
            print('Found new job {} - {}'.format(job.id, job.funcname))
            # do not start job if dsets are being moved
            if (active_move_dsets.intersection(jobdsets) or
                    active_move_files.intersection(jobfiles)):
                print('Deferring job since datasets {} or files {} being '
                      'moved in active '
                      'job'.format(active_move_dsets.intersection(jobdsets),
                                   active_move_files.intersection(jobfiles)))
                continue
            else:
                print('Executing job {}'.format(job.id))
                if job.id in job_ds_map:
                    [active_dsets.add(ds) for ds in job_ds_map[job.id]]
                if job.id in job_fn_map:
                    [active_files.add(fn) for fn in job_fn_map[job.id]]
                run_job(job, jobmap)


def run_job(job, jobmap):
    job.state = Jobstates.PROCESSING
    jobfunc = jobmap[job.funcname]['func']
    args = json.loads(job.args)
    kwargs = json.loads(job.kwargs)
    try:
        jobfunc(job.id, *args, **kwargs)
    except RuntimeError as e:
        print('Error occurred, trying again automatically in next round')
        job.state = Jobstates.ERROR
        JobError.objects.create(job_id=job.id, message=e)
        job.save()
    except Exception as e:
        print('Error occurred, not executing this job')
        job.state = Jobstates.ERROR
        JobError.objects.create(job_id=job.id, message=e)
        job.save()
    job.save()


def collect_filejob_activity():
    job_fn_map, active_move_files, active_files = {}, set(), set()
    for fj in FileJob.objects.select_related(
            'job', 'storedfile__rawfile__datasetrawfile__dataset').exclude(
            job__state=Jobstates.DONE):
        try:
            job_fn_map[fj.job_id].add(fj.storedfile_id)
        except KeyError:
            job_fn_map[fj.job_id] = set([fj.storedfile.id])
        if (fj.job.jobtype == Jobtypes.MOVE and
                fj.job.state in [Jobstates.PROCESSING, Jobstates.ERROR]):
            active_move_files.add(fj.storedfile.id)
            active_files.add(fj.storedfile.id)
        elif fj.job.state in [Jobstates.PROCESSING, Jobstates.ERROR]:
            active_files.add(fj.storedfile.id)
    return job_fn_map, active_move_files, active_files


def collect_dsjob_activity():
    job_ds_map, active_move_dsets, active_dsets = {}, set(), set()
    for dsj in DatasetJob.objects.select_related('job').exclude(
            job__state=Jobstates.DONE):
        try:
            job_ds_map[dsj.job_id].add(dsj.dataset_id)
        except KeyError:
            job_ds_map[dsj.job_id] = set([dsj.dataset_id])
        if (dsj.job.jobtype == Jobtypes.MOVE and
                dsj.job.state in [Jobstates.PROCESSING, Jobstates.ERROR]):
            active_move_dsets.add(dsj.dataset_id)
            active_dsets.add(dsj.dataset_id)
        elif dsj.job.state in [Jobstates.PROCESSING, Jobstates.ERROR]:
            active_dsets.add(dsj.dataset_id)
    return job_ds_map, active_move_dsets, active_dsets


def check_task_chain(task):
    chaintask = TaskChain.objects.filter(task=task)
    if chaintask:
        Task.objects.filter(pk__in=[
            tc.task_id for tc in TaskChain.objects.filter(
                lasttask=chaintask.get().lasttask)]).update(
                    state=states.FAILURE)


def process_job_tasks(job, jobtasks):
    job_updated, tasks_finished, tasks_failed = False, True, False
    # In case the job did not create tasks it may have been obsolete
    tasks_finished = True
    tasks_failed = False
    for task in jobtasks:
        if task.state != states.SUCCESS:
            tasks_finished = False
        if task.state == states.FAILURE:
            check_task_chain(task)
            tasks_failed = True
    if tasks_finished:
        print('All tasks finished, job {} done'.format(job.id))
        job.state = Jobstates.DONE
        job_updated = True
    elif tasks_failed:
        print('Failed tasks for job {}, setting to error'.format(job.id))
        job.state = Jobstates.ERROR
        job_updated = True
        # FIXME joberror msg needs to be set, in job or task?
    if job_updated:
        job.save()
    else:
        print('Job {} continues processing, no failed tasks'.format(job.id))
