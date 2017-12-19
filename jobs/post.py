import requests
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


def taskfail_update_db(task_id):
    update_db(urljoin(config.KANTELEHOST, reverse('jobs:taskfail')),
              {'task': task_id, 'client_id': config.APIKEY})


def save_task_chain(taskchain, job_id):
    chain_ids = []
    while taskchain.parent:
        chain_ids.append(taskchain.id)
        taskchain = taskchain.parent
    chain_ids.append(taskchain.id)
    for chain_id in chain_ids:
        t = Task(asyncid=chain_id, job_id=job_id, state=states.PENDING)
        t.save()
        TaskChain.objects.create(task_id=t.id, lasttask=chain_ids[0])
