import requests
import json
from urllib.parse import urljoin

from django.urls import reverse

from kantele import settings


def update_db(url, form=False, json=False, msg=False):
    try:
        if form:
            r = requests.post(url=url, data=form, verify=settings.CERTFILE)
        elif json:
            r = requests.post(url=url, json=json, verify=settings.CERTFILE)
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
    update_db(urljoin(settings.KANTELEHOST, reverse('jobs:taskfail')),
              json={'task': task_id, 'client_id': settings.APIKEY, 'msg': msg})


