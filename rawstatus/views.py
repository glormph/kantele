from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponseNotAllowed)
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


def check_producer(producer_id):
    return Producer.objects.get(client_id=producer_id)


def register_file(request):
    """Treats POST requests with:
        - client_id
        - filename
        - md5
        - date of production/acquisition
    """
    if request.method == 'POST':
        try:
            producer = check_producer(request.POST.client_id)
        except Producer.DoesNotExist:
            return HttpResponseForbidden()
        file_record = RawFile(request.fn, producer, request.md5, request.size,
                              request.date)
        # FIXME check if not already exist!
        file_record.save()
        return JsonResponse({'file_id': file_record.id, 'state': 'registered'})
    else:
        return HttpResponseNotAllowed()


def file_transferred(request):
    """Treats POST requests with:
        - fn_id
    Starts checking file MD5 in background
    """
    fn_id = request.POST.fn_id
    if request.method == 'POST':
        try:
            check_producer(request.POST.client_id)
        except Producer.DoesNotExist:
            return HttpResponseForbidden()
        try:
            file_transferred = TransferredFile.objects.get(fileid=fn_id)
        except TransferredFile.DoesNotExist:
            file_transferred = TransferredFile(fn_id)
            file_transferred.save()
            # FIXME start background process for MD5
            return JsonResponse({'fn_id': request.POST.fn_id,
                                 'md5_state': False})
        # FIXME rawfile has no file_id field in model, how?
        file_registered = RawFile(file_id=fn_id)
        # FIXME default value at not saved (NULL in db)? FAlse or None?
        if not file_transferred.md5:
            return JsonResponse({'fn_id': fn_id, 'md5_state': False})
        if file_registered.source_md5 == file_transferred.md5:
            return JsonResponse({'fn_id': fn_id, 'md5_state': 'ok'})
        else:
            return JsonResponse({'fn_id': fn_id, 'md5_state': 'error'})
    else:
        return HttpResponseNotAllowed()
