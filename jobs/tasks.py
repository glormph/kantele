import json

from celery import shared_task, states
from kantele.celery import app

from jobs.models import Task, Job, JobError
from jobs.jobs import Jobstates, Jobtypes
from datasets.models import DatasetJob
from jobs.jobs import jobmap


# FIXME there will also be search jobs and maybe others that span datasets,
# but this should be fixed now
# There are also multi-jobs on Dset from same user action (* add and remove
# files), they are currently waiting for the earlier job to finish.

@shared_task
def run_ready_jobs():
    print('Checking job queue')
    job_ds_map, active_move_dsets, active_dsets = collect_job_activity()
    print('{} jobs in queue, including errored jobs'.format(len(job_ds_map)))
    for job in Job.objects.order_by('timestamp').exclude(
            state__in=[Jobstates.DONE, Jobstates.ERROR]):
        jobdsets = job_ds_map[job.id]
        if job.state == Jobstates.PROCESSING:
            tasks = Task.objects.filter(job_id=job.id)
            if tasks.count() > 0:
                print('Updating task status for active job {}'.format(job.id))
                process_job_tasks(job, tasks)
        elif job.state == Jobstates.PENDING and job.jobtype == Jobtypes.MOVE:
            print('Found new move job')
            # do not start move job if there is activity on dset
            if active_dsets.intersection(jobdsets):
                print('Deferring move job since datasets {} are being used in '
                      'other job'.format(active_dsets.intersection(jobdsets)))
                continue
            else:
                print('Executing move job {}'.format(job.id))
                [active_dsets.add(ds) for ds in job_ds_map[job.id]]
                [active_move_dsets.add(ds) for ds in job_ds_map[job.id]]
                run_job(job, jobmap)
        elif job.state == Jobstates.PENDING:
            print('Found new job')
            # do not start job if dsets are being moved
            if active_move_dsets.intersection(jobdsets):
                print('Deferring job since datasets {} being moved in active '
                      'job'.format(active_move_dsets.intersection(jobdsets)))
                continue
            else:
                print('Executing job {}'.format(job.id))
                [active_dsets.add(ds) for ds in job_ds_map[job.id]]
                run_job(job, jobmap)


def run_job(job, jobmap):
    job.state = Jobstates.PROCESSING
    jobfunc = jobmap[job.funcname]['func']
    args = json.loads(job.args)
    kwargs = json.loads(job.kwargs)
    try:
        jobfunc(job.id, *args, **kwargs)
    except RuntimeError as e:
        job.state = 'error'
        JobError.objects.create(job_id=job.id, message=e,
                                autorequeue=jobmap[job.funcname]['retry'])
        job.save()
    except Exception as e:
        job.state = 'error'
        JobError.objects.create(job_id=job.id, message=e, autorequeue=False)
        job.save()
    job.save()


def collect_job_activity():
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


def process_job_tasks(job, jobtasks):
    job_updated, tasks_finished, tasks_failed = False, True, False
    for task in jobtasks:
        task_state = app.AsyncResult(task.asyncid).state
        if task_state != states.SUCCESS:
            tasks_finished = False
        if task_state == states.FAILURE:
            tasks_failed = True
        if task.state != task_state:
            task.state = task_state
            task.save()
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
