from datetime import datetime
import os

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse

from jobs.jobs import Jobstates, is_job_retryable
from jobs.models import Task
from datasets.models import DatasetJob
from rawstatus.models import FileJob


def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


def show_jobs(request):
    jobs = {}
    for task in Task.objects.select_related('job').filter(
            job__state__in=[Jobstates.PENDING, Jobstates.PROCESSING,
                        Jobstates.ERROR]):
        freshjob = {'name': task.job.funcname, 
                    'date': datetime.strftime(task.job.timestamp, '%Y%m%d'),
                    'retry': is_job_retryable(task.job), 'id': task.job.id,
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        if not task.job.state in jobs:
            jobs[task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in jobs[task.job.state]:
            jobs[task.job.state][task.job.id] = freshjob
        jobs[task.job.state][task.job.id]['tasks'][task.state] += 1
    dsfnjobmap = {}
    for dsj in DatasetJob.objects.select_related(
            'dataset__runname__experiment__project', 'dataset__user',
            'job').exclude(job__state=Jobstates.DONE):
        ds = dsj.dataset
        dsname = '{} - {} - {}'.format(ds.runname.experiment.project.name,
                                       ds.runname.experiment.name,
                                       ds.runname.name)
        if dsj.job_id not in dsfnjobmap:
            dsfnjobmap[dsj.job_id] = {
                'user': '{} {}'.format(ds.user.first_name, ds.user.last_name),
                'alttexts': [dsname]}
        else:
            dsfnjobmap[dsj.job_id]['alttexts'].append(dsname)
    for fnj in FileJob.objects.select_related('storedfile__rawfile__producer', 
            'job').exclude(job__state=Jobstates.DONE):
        fname = os.path.join(fnj.storedfile.servershare.name, fnj.storedfile.path,
                             fnj.storedfile.filename)
        dsfnjobmap[fnj.job_id] = {'user': fnj.storedfile.rawfile.producer.name,
                                  'alttexts': [fname]}
    for jstate in [Jobstates.PENDING, Jobstates.PROCESSING, Jobstates.ERROR]:
        if jstate in jobs:
            jobs[jstate] = [x for x in jobs[jstate].values()]
            for job in jobs[jstate]:
                job.update(dsfnjobmap[job['id']])
    return JsonResponse(jobs)
