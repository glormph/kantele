from celery import states
from jobs import models


def set_task_done(task_id):
    task = models.Task.objects.get(asyncid=task_id)
    task.state = states.SUCCESS
    task.save()


def taskclient_authorized(client_id, possible_ids):
    """Possibly use DB in future"""
    return client_id in possible_ids
