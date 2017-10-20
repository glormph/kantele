from celery import states
from jobs import models


def set_task_done(task_id):
    task = models.Task.get(asyncid=task_id)
    task.state = states.SUCCESS
    task.save()
