from celery import states
from django.http import (HttpResponseForbidden, HttpResponse,
                         HttpResponseNotAllowed)
from jobs import models
from kantele import settings as config


def set_task_done(task_id):
    task = models.Task.objects.get(asyncid=task_id)
    task.state = states.SUCCESS
    task.save()


def taskclient_authorized(client_id, possible_ids):
    """Possibly use DB in future"""
    return client_id in possible_ids


def task_failed(request):
    if not request.method == 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    if 'client_id' not in request.POST or not taskclient_authorized(
            request.POST['client_id'], config.CLIENT_APIKEYS):
        return HttpResponseForbidden()
    task = models.Task.objects.get(asyncid=request.POST['task_id'])
    task.state = states.FAILURE
    task.save()
    return HttpResponse()
