import requests
from urllib.parse import urljoin
from django.urls import reverse

from kantele import settings as config


def update_db(url, postdata, msg=False):
    try:
        r = requests.post(url=url, data=postdata, verify=config.CERTFILE)
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