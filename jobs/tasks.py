import json

from celery import shared_task, states
from kantele.celery import app

from jobs.models import Task, Job, JobError
from jobs.jobs import Jobstates, Jobtypes
from datasets.models import DatasetJob
from rawstatus.models import FileJob
from jobs.jobs import jobmap


# FIXME there will also be search jobs and maybe others that span datasets,
# but this should be fixed now
# There are also multi-jobs on Dset from same user action (* add and remove
# files), they are currently waiting for the earlier job to finish.


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
            # requeue waiting jobs
            joberror = JobError.objects.get(job_id=job.id)
            if joberror.autorequeue:
                print('Retrying job with autorequeue')
                joberror.delete()
                job.state = Jobstates.PENDING
                job.save() 
        if job.state == Jobstates.PROCESSING:
            tasks = Task.objects.filter(job_id=job.id)
            if tasks.count() > 0:
                print('Updating task status for active job {}'.format(job.id))
                process_job_tasks(job, tasks)
        elif job.state == Jobstates.PENDING and job.jobtype == Jobtypes.MOVE:
            print('Found new move job')
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
            print('Found new job')
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
        job.state = 'error'
        JobError.objects.create(job_id=job.id, message=e,
                                autorequeue=jobmap[job.funcname]['retry'])
        job.save()
    except Exception as e:
        print('Error occurred, not executing this job')
        job.state = 'error'
        JobError.objects.create(job_id=job.id, message=e, autorequeue=False)
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


def process_job_tasks(job, jobtasks):
    job_updated, tasks_finished, tasks_failed = False, True, False
    for task in jobtasks:
        if task.state != states.SUCCESS:
            tasks_finished = False
        if task.state == states.FAILURE:
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
