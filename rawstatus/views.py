from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponseNotAllowed, HttpResponse)
from django.shortcuts import render

from kantele import settings as config
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare,
                              SwestoreBackedupFile)
from jobs import jobs as jobutil
from jobs.views import set_task_done, taskclient_authorized
from datetime import datetime


def show_files(request):
    storedfiles = {x.rawfile.id: hasattr(x, 'swestorebackedupfile') for x in
                   StoredFile.objects.exclude(md5='').select_related(
                       'rawfile', 'swestorebackedupfile')}
    files = []
    for fn in RawFile.objects.order_by('date').select_related(
            'producer').reverse()[:100]:
        files.append({'name': fn.name, 'prod': fn.producer.name, 'date': fn.date,
                      'size': round(fn.size / (2**20), 1), 'transfer': fn.id in storedfiles,
                      'backup': fn.id in storedfiles and storedfiles[fn.id]})
    return render(request, 'rawstatus/files.html', {'files': files})


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
            fname = request.POST['filename']
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
        except RawFile.DoesNotExist:
            print('File has not been registered yet, cannot transfer')
            return JsonResponse({'fn_id': request.POST['fn_id'],
                                 'state': 'error'})
        try:
            file_transferred = StoredFile.objects.get(rawfile_id=fn_id,
                                                      filetype=ftype)
        except StoredFile.DoesNotExist:
            print('New transfer registered, fn_id {}'.format(fn_id))
            file_transferred = StoredFile(rawfile_id=fn_id, filetype=ftype,
                                          servershare=tmpshare, path='',
                                          filename=fname, md5='')
            file_transferred.save()
            jobutil.create_file_job('get_md5', file_transferred.id)
        else:
            print('File already registered as transfer, client asks for new '
                  'MD5 check after a possible retransfer. Running MD5 check.')
            jobutil.create_file_job('get_md5', file_transferred.id)
        finally:
            return JsonResponse({'fn_id': request.POST['fn_id'],
                                 'state': 'ok'})
    else:
        return HttpResponseNotAllowed(permitted_methods=['POST'])


def check_md5_success(request):
    if not request.method == 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    try:
        fn_id = request.GET['fn_id']
        ftype = request.GET['ftype']
        client_id = request.GET['client_id']
    except KeyError:
        return HttpResponseForbidden()
    try:
        check_producer(client_id)
    except Producer.DoesNotExist:
        return HttpResponseForbidden()
    print('Transfer state requested for fn_id {}'.format(fn_id))
    file_transferred = StoredFile.objects.get(rawfile_id=fn_id,
                                              filetype=ftype)
    file_registered = file_transferred.rawfile
    if not file_transferred.md5:
        return JsonResponse({'fn_id': fn_id, 'md5_state': False})
    if (file_registered.source_md5 == file_transferred.md5 and
            SwestoreBackedupFile.objects.filter(
            storedfile_id=file_transferred.id).count() == 0):
        jobutil.create_file_job('create_swestore_backup', file_transferred.id,
                                file_transferred.md5)
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'error'})


def set_md5(request):
    if 'client_id' not in request.POST or not taskclient_authorized(
            request.POST['client_id'], [config.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    storedfile = StoredFile.objects.get(pk=request.POST['sfid'])
    storedfile.md5 = request.POST['md5']
    storedfile.save()
    print('stored file saved')
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
        print('MD5 saved')
    return HttpResponse()


def created_swestore_backup(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.SWESTORECLIENT_APIKEY]):
        return HttpResponseForbidden()
    backup = SwestoreBackedupFile.objects.filter(storedfile_id=data['sfid'])
    backup.update(swestore_path=data['swestore_path'], success=True)
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


def update_storagepath_file(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    if 'fn_id' in data:
        sfile = StoredFile.objects.get(pk=data['fn_id'])
        sfile.servershare = ServerShare.objects.get(name=data['servershare'])
        sfile.path = data['dst_path']
        sfile.save()
    elif 'fn_ids' in data:
        StoredFile.objects.filter(pk__in=data['fn_ids']).update(
            path=data['dst_path'])
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


def delete_storedfile(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.SWESTORECLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.filter(pk=data['fn_id']).select_related(
        'rawfile').get()
    if sfile.filetype == 'raw':
        sfile.rawfile.deleted = True
        sfile.rawfile.save()
    sfile.delete()
    return HttpResponse()


def created_mzml(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile(rawfile_id=data['rawfile_id'], filetype='mzml',
                       path=data['path'], filename=data['filename'],
                       md5=data['md5'])
    sfile.servershare = ServerShare.objects.get(name=data['servershare'])
    sfile.save()
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()
