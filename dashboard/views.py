from datetime import datetime

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse

from jobs.jobs import Jobstates, is_job_retryable
from jobs.models import Task


def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


def show_jobs(request):
    jobs = {}
    for task in Task.objects.filter(
            job__state__in=[Jobstates.PENDING, Jobstates.PROCESSING,
                        Jobstates.ERROR]):
        freshjob = {'name': task.job.funcname, 'user': 'TBD',
                    'date': datetime.strftime(task.job.timestamp, '%Y%m%d'),
                    'retry': is_job_retryable(task.job),
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        if not task.job.state in jobs:
            jobs[task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in jobs[task.job.state]:
            jobs[task.job.state][task.job.id] = freshjob
        jobs[task.job.state][task.job.id]['tasks'][task.state] += 1
    for jstate in [Jobstates.PENDING, Jobstates.PROCESSING, Jobstates.ERROR]:
        if jstate in jobs:
            jobs[jstate] = [x for x in jobs[jstate].values()]
    return JsonResponse(jobs)
