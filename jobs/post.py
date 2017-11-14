import requests
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
