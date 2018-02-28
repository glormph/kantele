from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponseNotAllowed)
from django.shortcuts import render

from kantele import settings
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare,
                              SwestoreBackedupFile)
from analysis.models import Analysis, SearchFiles
from datasets import views as dsviews
from jobs import jobs as jobutil
from datetime import datetime


def show_files(request):
    files = []
    for sfn in StoredFile.objects.filter(
            filetype='raw', checked=False).select_related('rawfile'):
        fn = sfn.rawfile
        files.append({'name': fn.name, 'prod': fn.producer.name,
                      'date': fn.date, 'backup': False,
                      'size': round(fn.size / (2**20), 1), 'transfer': False})
    for sfn in SwestoreBackedupFile.objects.select_related(
            'storedfile__rawfile').filter(success=False):
        fn  = sfn.storedfile.rawfile
        files.append({'name': fn.name, 'prod': fn.producer.name, 'date': fn.date,
                      'size': round(fn.size / (2**20), 1), 'backup': False,
                      'transfer': sfn.storedfile.checked})
    for sfn in SwestoreBackedupFile.objects.order_by(
            'storedfile__rawfile__date').select_related(
            'storedfile__rawfile').filter(success=True).exclude(
            storedfile__checked=False).reverse()[:100]:
        fn  = sfn.storedfile.rawfile
        files.append({'name': fn.name, 'prod': fn.producer.name, 'date': fn.date,
                      'size': round(fn.size / (2**20), 1), 'backup': True,
                      'transfer': True})
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
        tmpshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
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
                                          filename=fname, md5='', checked=False)
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
    elif file_registered.source_md5 == file_transferred.md5:
        if not file_transferred.checked:
            file_transferred.checked = True
            file_transferred.save()
        if SwestoreBackedupFile.objects.filter(
                storedfile_id=file_transferred.id).count() == 0:
            jobutil.create_file_job('create_swestore_backup',
                                    file_transferred.id, file_transferred.md5)
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'error'})


def add_to_qc(rawfile, storedfile):
    # add file to dataset if not exist ds yet: proj:QC, exp:Hela, run:instrument
    data = {'dataset_id': False, 'experiment_id': settings.INSTRUMENT_QC_EXP,
            'project_id': settings.INSTRUMENT_QC_PROJECT,
            'runname_id': settings.INSTRUMENT_QC_RUNNAME}
    dset = dsviews.get_or_create_qc_dataset(data)
    data['dataset_id'] = dset.id
    data['removed_files'] = {}
    data['added_files'] = {1: {'id': rawfile.id}}
    dsviews.save_or_update_files(data)
    jobutil.create_dataset_job('convert_mzml', dset.id)
    analysis = Analysis(
        user_id=settings.QC_USER_ID, search_id=settings.QC_SEARCH_ID,
        account_id=settings.GALAXY_ACCOUNT_ID, params=settings.QC_PARAMS_ID,
        name='{}_{}'.format(storedfile.rawfile.producer.name,
                            dset.runname.experiment.name))
    analysis.save()
    SearchMzmlFiles.objects.create(analysis_id=analysis.id,
                                   mzml_id=file_transferred.id)
    jobutil.create_file_job('run_longit_qc_workflow', file_transferred.id,
                            analysis.id)
