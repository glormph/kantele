import json

from celery import shared_task, states
from kantele.celery import app

from jobs.models import Task
from datasets.models import DatasetJob
from datasets.jobs import jobmap


# FIXME there will also be search jobs and maybe others that span datasets

@shared_task
def job_checker(*args):
    # check dataset jobs:
    dsjobs = DatasetJob.objects.select_related('job').exclude(
        state='done').order_by('-job__timestamp')
    activejobs = {}
    for dsj in dsjobs:
        try:
            activejobs[dsj.dataset_id].append(dsj.job)
        except:
            activejobs[dsj.dataset_id] = [dsj.job]
    for ds_id, jobs in activejobs.items():
        #run_this_job = True
        for job_to_run in jobs:
            jobtasks = Task.objects.filter(job_id=job_to_run.id).exclude(
                state__in=states.READY_STATES)
            if jobtasks.count():
                # there are tasks for this job, check tasks, update DB
                tasks_finished = True
                for task in jobtasks:
                    task_state = app.AsyncResult(task.asyncid).state
                    if task_state not in states.READY_STATES:
                        tasks_finished = False
                    if task.state != task_state:
                        task.state = task_state
                        task.save()
                if not tasks_finished:
                    # goto next dset
                    # FIXME ready states includes fail and failure should
                    # block next-job operations
                    break
                continue  # go to next job
            else:
                # no tasks for this job, run it and go to next dataset
                jobfunc = jobmap[job_to_run.name]
                args = json.loads(job_to_run.args)
                kwargs = json.loads(job_to_run.kwargs)
                jobfunc(job_to_run, args, kwargs)
                print('job 1 queued for dset {}: {}'.format(
                    ds_id, job_to_run.function))
