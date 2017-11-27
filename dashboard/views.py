from django.shortcuts import render

from jobs.jobs import Jobstates
from jobs.models import Task


def show_jobs(request):
    context = {'jobs': {}}
    for task in Task.objects.filter(
            job__state__in=[Jobstates.PENDING, Jobstates.PROCESSING,
                        Jobstates.ERROR]):
        freshjob = {'name': task.job.funcname, 'user': 'TBD',
                    'date': task.job.timestamp,
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        if not task.job.state in context['jobs']:
            context['jobs'][task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in context['jobs'][task.job.state]:
            context['jobs'][task.job.state][task.job.id] = freshjob
        context['jobs'][task.job.state][task.job.id]['tasks'][task.state] += 1
    for jstate in [Jobstates.PENDING, Jobstates.PROCESSING, Jobstates.ERROR]:
        if jstate in context['jobs']:
            context['jobs'][jstate] = context['jobs'][jstate].values()
    return render(request, 'dashboard/dashboard.html', context)
