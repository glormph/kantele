import json

from celery import shared_task

from jobs.models import Job
from datasets import jobs as dsjobs


# FIXME there will also be search jobs and maybe others that span datasets

@shared_task
def job_checker(*args):
    activejobs = Job.objects.exclude(state='done')
    # FIXME sort and check which one
    job_to_run = activejobs[0]
    jobfunc = dsjobs.jobmap[job_to_run.name]
    args = json.loads(job_to_run.args)
    kwargs = json.loads(job_to_run.kwargs)
    jobfunc(args, kwargs)
