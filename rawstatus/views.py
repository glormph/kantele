from django.http import HttpResponse
from filetracker import (RawFile, Producer, TransferredFile)

# FLow is like this:
# POST fn/md5/instrument/aqcuis.date
    # response JSON, with tmpfn or datedir, as to not overwrite
    # (client SCPs, if success)
# POST scp complete
    # response JSON
    # check MD5 in background
# GET is-md5-ok-of-fn-with-id?
    # response JSON with true or false

# FIXME need auth API key, or client UUID?


def register_file(request):
    """Treats POST requests with:
        - client_id
        - filename
        - md5
        - date of production/acquisition
    """
    if request.method == 'POST':
        # FIXME if not correct producer id, return 403
        producer = Producer.objects.get(client_id=request.POST.client_id)
        file_record = RawFile(request.fn, producer, request.md5, request.size,
                              request.date)
        file_record.save()
        # FIXME JSON {'file_id': f_id, 'state': 'registered'}
        return HttpResponse()
    else:
        # throw error 403 HTTP  FIXME
        return HttpResponse()


def file_transferred(request):
    """Treats POST requests with:
        - fn_id
    Starts checking file MD5 in background
    """
    if request.method == 'POST':
        # FIXME if not correct producer id, return 403
        file_transferred = RawFile(request.fn_id)
        file_transferred.save()
        # FIXME background process for MD5
        return HttpResponse()  # FIXME 200
    elif request.method == 'GET':
        fn_id = request.GET.fn_id
        # FIXME rawfile has no file_id field in model, how?
        file_registered = RawFile(file_id=fn_id)
        filestate_db = TransferredFile.objects.get(file_id=fn_id)
        # FIXME default value at not saved (NULL in db)? FAlse or None?
        if not filestate_db.md5:
            pass
            # FIXME 200 JSON {'fn_id': fn_id, 'md5_state': False}
        if file_registered.source_md5 == filestate_db.md5:
            pass
            # FIXME 200 JSON {'fn_id': fn_id, 'md5_state': 'ok'
        else:
            pass
            # FIXME 200 JSON {'fn_id': fn_id, 'md5_state': 'error'
        return

    else:
        # throw error 403 HTTP  FIXME
        return HttpResponse()
