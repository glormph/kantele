import requests
import json
from urllib.parse import urljoin

from django.urls import reverse
from celery import states

from kantele import settings as config
from jobs.models import Task, TaskChain


def update_db(url, form=False, json=False, msg=False):
    try:
        if form:
            r = requests.post(url=url, data=form, verify=config.CERTFILE)
        elif json:
            r = requests.post(url=url, json=json, verify=config.CERTFILE)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        if not msg:
            msg = 'Could not update database: {}'
        msg = msg.format(e)
        print(msg)
        raise RuntimeError(msg)
    else:
        return r


def taskfail_update_db(task_id, msg=False):
    update_db(urljoin(config.KANTELEHOST, reverse('jobs:taskfail')),
              {'task': task_id, 'client_id': config.APIKEY, 'msg': msg})


def save_task_chain(taskchain, args, job_id):
    chain_ids = []
    while taskchain.parent:
        chain_ids.append(taskchain.id)
        taskchain = taskchain.parent
    chain_ids.append(taskchain.id)
    for chain_id, arglist in zip(chain_ids, args):
        t = create_db_task(chain_id, job_id, *arglist)
        TaskChain.objects.create(task_id=t.id, lasttask=chain_ids[0])


def create_db_task(task_id, job_id, *args, **kwargs):
    strargs = json.dumps([args, kwargs])
    t = Task(asyncid=task_id, job_id=job_id, state=states.PENDING, args=strargs)
    t.save()
    return t
