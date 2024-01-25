"""
These tasks are to be run by the celery beat automatic task runner every 10 seconds or so.
It contains a VERY SIMPLE job scheduler. The more advanced job scheduling is to be done by
celery chains etc, Nextflow, or Galaxy or whatever one likes.

Scheduler runs sequential and waits for each job that contains files running in another job
"""

from celery import states
from celery.result import AsyncResult
from django.core.management.base import BaseCommand
from time import sleep

from kantele import settings
from jobs.models import Task, Job, JobError, TaskChain
from jobs.jobs import Jobstates, send_slack_message
from jobs import jobs as jj
from rawstatus.models import FileJob
from jobs.views import jobmap


class Command(BaseCommand):
    help = 'Run job runner until you terminate it'

    def handle(self, *args, **options):
        '''Only run once when in testing mode, so it returns'''
        if settings.TESTING:
            run_ready_jobs()
        else:
            while True:
                run_ready_jobs()
                sleep(settings.JOBRUNNER_INTERVAL)


def run_ready_jobs():
    print('Checking job queue')
    jobs_not_finished = Job.objects.order_by('timestamp').exclude(
        state__in=jj.JOBSTATES_DONE + [Jobstates.WAITING])
    job_fn_map, active_files = process_job_file_activity(jobs_not_finished)
    print('{} jobs in queue, including errored jobs'.format(jobs_not_finished.count()))
    for job in jobs_not_finished:
        print('Job {}, state {}'.format(job.id, job.state))
        # Just print info about ERROR-jobs, but also process tasks
        job.refresh_from_db()
        if job.state == Jobstates.ERROR:
            print('ERROR MESSAGES:')
            tasks = Task.objects.filter(job_id=job.id)
            process_job_tasks(job, tasks)
            for joberror in JobError.objects.filter(job_id=job.id):
                print(joberror.message)
            print('END job error messages')
        elif job.state == Jobstates.REVOKING:
            jwrapper = jobmap[job.funcname](job.id) 
            if jwrapper.revokable:
                for task in job.task_set.all():
                    AsyncResult(task.asyncid).revoke(terminate=True, signal='SIGUSR1')
                    task.state = states.REVOKED
                    task.save()
            job.state = Jobstates.CANCELED
            job.save()
        # Ongoing jobs get updated
        elif job.state == Jobstates.PROCESSING:
            tasks = Task.objects.filter(job_id=job.id)
            print('Updating task status for active job {} - {}'.format(job.id, job.funcname))
            process_job_tasks(job, tasks)
        # Pending jobs are trickier, wait queueing until any previous job on same files
        # is finished. Errored jobs thus block pending jobs if they are on same files.
        elif job.state == Jobstates.PENDING:
            print('Found new job {} - {}'.format(job.id, job.funcname))
            jobfiles = job_fn_map[job.id] if job.id in job_fn_map else set()
            # do not start job if there is activity on files
            if active_files.intersection(jobfiles):
                print('Deferring job since files {} are being used in '
                      'other job'.format(active_files.intersection(jobfiles)))
                continue
            # Only add jobs with files (some jobs have none!) to "active_files"
            # FIXME do some jobs really have no files?
            if job.id in job_fn_map:
                [active_files.add(fn) for fn in job_fn_map[job.id]]
            run_job(job, jobmap)


def run_job(job, jobmap):
    print('Executing job {}'.format(job.id))
    job.state = Jobstates.PROCESSING
    jwrapper = jobmap[job.funcname](job.id) 
    try:
        jwrapper.run(**job.kwargs)
    except RuntimeError as e:
        print('Error occurred, trying again automatically in next round')
        job.state = Jobstates.ERROR
        JobError.objects.create(job_id=job.id, message=e)
        job.save()
    except Exception as e:
        print(f'Error occurred: {e} --- not executing this job')
        job.state = Jobstates.ERROR
        JobError.objects.create(job_id=job.id, message=e)
        job.save()
        if not settings.TESTING:
            send_slack_message('Job {} failed in job runner: {}'.format(job.id, job.funcname), 'kantele')
    else:
        # Defensive save() calls above in excepts, in case we ever want to raise or something
        job.save()


def process_job_file_activity(nonready_jobs):
    job_fn_map, active_files = {}, set()
    for job in nonready_jobs:
        fjs = job.filejob_set.all()
        if not fjs.count():
            fjs = []
            jwrapper = jobmap[job.funcname](job.id) 
            for sf_id in jwrapper.get_sf_ids_jobrunner(**job.kwargs):
                # FIXME create file job in job creation instead of here??
                newfj = FileJob(storedfile_id=sf_id, job_id=job.id)
                newfj.save()
                fjs.append(newfj)
        for fj in fjs:
            try:
                job_fn_map[job.id].add(fj.storedfile_id)
            except KeyError:
                job_fn_map[job.id] = set([fj.storedfile_id])
            if job.state in [Jobstates.PROCESSING, Jobstates.ERROR]:
                active_files.add(fj.storedfile_id)
    #for fj in FileJob.objects.select_related('job').filter(job__in=nonready_jobs):
    return job_fn_map, active_files


def set_task_chain_error(task):
    chaintask = TaskChain.objects.filter(task=task)
    if chaintask:
        Task.objects.filter(pk__in=[
            tc.task_id for tc in TaskChain.objects.filter(
                lasttask=chaintask.get().lasttask)]).update(
                    state=states.FAILURE)


def process_job_tasks(job, jobtasks):
    """Updates job state based on its task status"""
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
            set_task_chain_error(task)
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
        if job.state != Jobstates.ERROR:
            send_slack_message('Tasks for job {} failed: {}'.format(job.id, job.funcname), 'kantele')
        job.state = Jobstates.ERROR
        job_updated = True
        # FIXME joberror msg needs to be set, in job or task?
    if job_updated:
        job.save()
    else:
        print('Job {} continues processing, no failed tasks'.format(job.id))
