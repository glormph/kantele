"""
These tasks are to be run by the celery beat automatic task runner every 10 seconds or so.
It contains a VERY SIMPLE job scheduler. The more advanced job scheduling is to be done by
celery chains etc, Nextflow, or Galaxy or whatever one likes.

The scheduling here includes:
Jobs that are of type MOVE will wait for other jobs on those files
Jobs that are of another type (PROCESS, UPLOAD), will wait for MOVE jobs on those files
"""

import json

from celery import shared_task, states

from kantele import settings
from jobs.models import Task, Job, JobError, TaskChain
from jobs.jobs import Jobstates, Jobtypes, jobmap
from rawstatus.models import FileJob


@shared_task
def run_ready_jobs():
    print('Checking job queue')
    jobs_not_finished = Job.objects.order_by('timestamp').exclude(
        state__in=[Jobstates.DONE, Jobstates.WAITING])
    job_fn_map, active_move_files, active_files = collect_job_file_activity(jobs_not_finished)
    print('{} jobs in queue, including errored jobs'.format(jobs_not_finished.count()))
    for job in jobs_not_finished:
        jobfiles = job_fn_map[job.id] if job.id in job_fn_map else set()
        print('Job {}, state {}, type {}'.format(job.id, job.state, job.jobtype))
        if job.state == Jobstates.ERROR:
            print('ERROR MESSAGES:')
            tasks = Task.objects.filter(job_id=job.id)
            process_job_tasks(job, tasks)
            for joberror in JobError.objects.filter(job_id=job.id):
                print(joberror.message)
            print('END error messages')
        elif job.state == Jobstates.PROCESSING:
            tasks = Task.objects.filter(job_id=job.id)
            print('Updating task status for active job {} - {}'.format(job.id, job.funcname))
            process_job_tasks(job, tasks)
        # FIXME Changed this, test it:
        # why do we have a non-move job where we do not have to wait at all?
        # scenario? is basically non-dep simulation based on jobtype which is bad
        # like so, md5 on transferred QC is not done yet, qc jobs are queued. Move file, mzmlconv is not done
        # bc file to move has job on it (md5), but qc job (process) is launched. Bam! error: there is no mzML.
        # what do we lose if we just make all jobs wait instead?
        # scenario all jobs wait: somewhere eternal wait? TESTING
        elif job.state == Jobstates.PENDING: #and job.jobtype == Jobtypes.MOVE:
            print('Found new job {} - {}'.format(job.id, job.funcname))
            # do not start move job if there is activity on files
            if active_files.intersection(jobfiles):
                print('Deferring move job since files {} are being used in '
                      'other job'.format(active_files.intersection(jobfiles)))
                continue
            else:
                [active_files.add(fn) for fn in job_fn_map[job.id]]
                [active_move_files.add(fn) for fn in job_fn_map[job.id]]
                run_job(job, jobmap)
#        elif job.state == Jobstates.PENDING:
#            print('Found new job {} - {}'.format(job.id, job.funcname))
#            # do not start job if files are being moved
#            if active_move_files.intersection(jobfiles):
#                print('Deferring job since files {} being moved in active '
#                      'job'.format(active_move_files.intersection(jobfiles)))
#                continue
#            else:
#                [active_files.add(fn) for fn in job_fn_map[job.id]]
#                run_job(job, jobmap)


def run_job(job, jobmap):
    print('Executing job {} of type {}'.format(job.id, job.jobtype))
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


def collect_job_file_activity(nonready_jobs):
    job_fn_map, active_move_files, active_files = {}, set(), set()
    for fj in FileJob.objects.select_related('job', 'storedfile').filter(
            job__in=nonready_jobs):
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
    no_tasks_for_job = True
    for task in jobtasks:
        no_tasks_for_job = False
        if task.state != states.SUCCESS:
            tasks_finished = False
        if task.state == states.FAILURE:
            check_task_chain(task)
            tasks_failed = True
    if no_tasks_for_job and job.state == Jobstates.ERROR:
        # Jobs that error before task registration should not get set to done!
        pass
    elif tasks_finished and job.state != Jobstates.ERROR:
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
