from django.db.utils import IntegrityError
from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponseNotAllowed)
from django.core.exceptions import ObjectDoesNotExist
from rawstatus.models import (RawFile, Producer, TransferredFile)
from rawstatus import tasks
from datetime import datetime


# Create your views here.
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
            client_id = request.POST['client_id']
            fn = request.POST['fn']
            size = request.POST['size']
            md5 = request.POST['md5']
            filedate_raw = request.POST['date']
            file_date = datetime.strptime(filedate_raw, '%Y%m%d.%H:%M')
        except KeyError as error:
            print('POST request to register_file with missing parameter, '
                  '{}'.format(error))
            return HttpResponseForbidden()
        try:
            producer = check_producer(client_id)
        except Producer.DoesNotExist:
            print('POST request with incorrect client id '
                  '{}'.format(request.POST['client_id']))
            return HttpResponseForbidden()
        except ValueError as error:
            print('POST request to register_file with incorrect formatted '
                  'date parameter {}'.format(error))
            return HttpResponseForbidden()
        file_record = RawFile(name=fn, producer=producer, source_md5=md5,
                              size=size, date=file_date)
        try:
            file_record.save()
        except IntegrityError:
            # FIXME make a response with existing id and state?
            existing_fn = RawFile.objects.get(source_md5=md5)
            print('File already exists', existing_fn)
            return HttpResponseForbidden()
            #return JsonResponse(
        return JsonResponse({'file_id': file_record.id, 'state': 'registered'})
    else:
        return HttpResponseNotAllowed(permitted_methods=['POST'])


def file_transferred(request):
    """Treats POST requests with:
        - fn_id
    Starts checking file MD5 in background
    """
    if request.method == 'POST':
        try:
            fn_id = request.POST['fn_id']
            client_id = request.POST['client_id']
        except KeyError as error:
            print('POST request to register_file with missing parameter, '
                  '{}'.format(error))
            return HttpResponseForbidden()
        try:
            check_producer(client_id)
        except Producer.DoesNotExist:
            return HttpResponseForbidden()
        try:
            file_transferred = TransferredFile.objects.get(rawfile_id=fn_id)
        except ObjectDoesNotExist:
            # FIXME fnpath
            print('New transfer registered, fn_id {}'.format(fn_id))
            file_transferred = TransferredFile(rawfile_id=fn_id)
            file_transferred.save()
            # FIXME start background process for MD5, unimplemented, call w
            # delay,
            tasks.get_md5(file_transferred.rawfile.id)
            return JsonResponse({'fn_id': request.POST.fn_id,
                                 'md5_state': False})
        print('Transfer state requested for fn_id {}'.format(fn_id))
        file_registered = file_transferred.rawfile
        if not file_transferred.md5:
            return JsonResponse({'fn_id': fn_id, 'md5_state': False})
        if file_registered.source_md5 == file_transferred.md5:
            return JsonResponse({'fn_id': fn_id, 'md5_state': 'ok'})
        else:
            return JsonResponse({'fn_id': fn_id, 'md5_state': 'error'})
    else:
        return HttpResponseNotAllowed()
