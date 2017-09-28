import json

from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponseNotAllowed, HttpResponse)
from django.contrib.auth.decorators import login_required

from kantele import settings as config
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare)
from rawstatus import tasks
from datetime import datetime


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
        try:
            file_date = datetime.strftime(
                datetime.fromtimestamp(float(filedate_raw)), '%Y-%m-%d %H:%M')
        except ValueError as error:
            print('POST request to register_file with incorrect formatted '
                  'date parameter {}'.format(error))
            return HttpResponseForbidden()
        try:
            existing_fn = RawFile.objects.get(source_md5=md5)
        except RawFile.DoesNotExist:
            file_record = RawFile(name=fn, producer=producer, source_md5=md5,
                                  size=size, date=file_date, claimed=False)
            file_record.save()
        else:
            stored = True if StoredFile.objects.select_related(
                'rawfile').filter(rawfile__source_md5=md5).count() else False
            msg = ('File {} is already registered and has MD5 {}. It is {}'
                   'stored'.format(existing_fn.name, existing_fn.source_md5,
                                   '' if stored else 'not '))
            print(msg)
            response = {'stored': stored, 'md5': existing_fn.source_md5,
                        'msg': msg}
            response['state'] = 'registered' if stored else 'error'
            if existing_fn.source_md5 == md5:
                response['file_id'] = existing_fn.id
            return JsonResponse(response)
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
            ftype = request.POST['ftype']
        except KeyError as error:
            print('POST request to register_file with missing parameter, '
                  '{}'.format(error))
            return HttpResponseForbidden()
        try:
            check_producer(client_id)
        except Producer.DoesNotExist:
            return HttpResponseForbidden()
        tmpshare = ServerShare.objects.get(name=config.TMPSHARENAME)
        try:
            RawFile.objects.get(pk=fn_id)
            file_transferred = StoredFile.objects.get(rawfile_id=fn_id,
                                                      filetype=ftype)
        except RawFile.DoesNotExist:
            print('File has not been registered yet, cannot transfer')
        except StoredFile.DoesNotExist:
            print('New transfer registered, fn_id {}'.format(fn_id))
            file_transferred = StoredFile(rawfile_id=fn_id, filetype=ftype,
                                          servershare=tmpshare, path='',
                                          md5='')
            file_transferred.save()
            tasks.get_md5.delay(file_transferred.id, '', tmpshare.name,
                                request.POST['filename'])
            return JsonResponse({'fn_id': request.POST['fn_id'],
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


def set_md5(request):
    storedfile = StoredFile.objects.get(pk=request.POST['sfid'])
    storedfile.md5 = request.POST['md5']
    storedfile.save()
    return HttpResponse()


@login_required
def update_filepath(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed()
    data = json.loads(request.body.decode('utf-8'))
    StoredFile.objects.filter(pk=data['fn_id']).update(path=data['path'])
    return HttpResponse()
