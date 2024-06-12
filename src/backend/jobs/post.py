import requests
import json
from urllib.parse import urljoin
from celery import states

from django.urls import reverse

from kantele import settings


def update_db(url, form=False, json=False, files=False, msg=False):
    try:
        r = False
        if form:
            r = requests.post(url=url, data=form)
        elif json:
            r = requests.post(url=url, json=json)
        elif files:
            r = requests.post(url=url, files=files)
        r.raise_for_status()
    except (requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError) as e:
        # BOOM YOU'RE DEAD
        if not msg:
            msg = 'Could not update database: {}'
        msg = msg.format(e)
        print(msg)
        raise RuntimeError(msg)
    else:
        if r:
            return r
        else:
            raise RuntimeError('Something went wrong')



def task_finished(task_id):
    update_db(urljoin(settings.KANTELEHOST, reverse('jobs:settask')), json={'task_id': task_id,
        'client_id': settings.APIKEY, 'state': states.SUCCESS})


def taskfail_update_db(task_id, msg=False):
    update_db(urljoin(settings.KANTELEHOST, reverse('jobs:settask')), json={'task_id': task_id,
        'client_id': settings.APIKEY, 'msg': msg, 'state': states.FAILURE})
