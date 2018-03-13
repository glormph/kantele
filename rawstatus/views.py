from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponse, HttpResponseNotAllowed)
from django.shortcuts import render

from kantele import settings
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare,
                              SwestoreBackedupFile)
from analysis.models import (Analysis, NextflowWorkflow, NextflowSearch,
                             SearchFile, LibraryFile)
from datasets import views as dsviews
from datasets import models as dsmodels
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
            fn = file_transferred.filename
            if 'QC' in fn and 'hela' in fn.lower() and any([x in fn for x in ['QE', 'HFLu', 'HFLe', 'Velos']]):
                singlefile_qc(file_transferred.rawfile, file_transferred)
            jobutil.create_file_job('create_swestore_backup',
                                    file_transferred.id, file_transferred.md5)
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': fn_id, 'md5_state': 'error'})


def singlefile_qc(rawfile, storedfile):
    """This method is only run for detecting new incoming QC files"""
    add_to_qc(rawfile, storedfile)
    jobutil.create_file_job('convert_single_mzml', storedfile.id)
    start_qc_analysis(rawfile, storedfile, settings.LONGQC_NXF_WF_ID,
                      settings.LONGQC_FADB_ID)


def manyfile_qc(rawfiles, storedfiles):
    """For reanalysis or batching by hand"""
    for rawfn, sfn in zip(rawfiles, storedfiles):
        try:
            dsmodels.DatasetRawFile.objects.select_related(
                'dataset').filter(rawfile=rawfn).get().dataset
        except dsmodels.DatasetRawFile.DoesNotExist:
            dset = add_to_qc(rawfn, sfn)
            print('Added QC file {} to QC dataset {}'.format(rawfn.id, dset.id))
        jobutil.create_file_job('convert_single_mzml', sfn.id)
    # Do not rerun with the same workflow as previously
    nfwf = NextflowWorkflow.objects.get(pk=settings.LONGQC_NXF_WF_ID)
    for rawfn, sfn in zip(rawfiles, storedfiles):
        searchfiles_with_current_qcnf = SearchFile.objects.filter(
            sfile__in=StoredFile.objects.select_related('rawfile').filter(
                filetype='mzml', rawfile_id=rawfn.id),
            search__in=NextflowSearch.objects.filter(nfworkflow=nfwf))
        if not searchfiles_with_current_qcnf.count():
            start_qc_analysis(rawfn, sfn, nfwf.id, settings.LONGQC_FADB_ID)
        else:
            print('QC has already been done with this workflow (id: {}) for '
                  'rawfile id {}'.format(nfwf.id, rawfn.id))


def add_to_qc(rawfile, storedfile):
    # add file to dataset: proj:QC, exp:Hela, run:instrument
    try:
        runname = dsmodels.RunName.objects.get(
            experiment_id=settings.INSTRUMENT_QC_EXP, name=rawfile.producer.name)
    except dsmodels.RunName.DoesNotExist:
        runname = dsmodels.RunName.objects.create(
            experiment_id=settings.INSTRUMENT_QC_EXP, name=rawfile.producer.name)
    data = {'dataset_id': False, 'experiment_id': settings.INSTRUMENT_QC_EXP,
            'project_id': settings.INSTRUMENT_QC_PROJECT,
            'runname_id': runname.id}
    dset = dsviews.get_or_create_qc_dataset(data)
    data['dataset_id'] = dset.id
    data['removed_files'] = {}
    data['added_files'] = {1: {'id': rawfile.id}}
    dsviews.save_or_update_files(data)
    return dset


def start_qc_analysis(rawfile, storedfile, wf_id, dbfn_id):
    analysis = Analysis(user_id=settings.QC_USER_ID, 
                        name='{}_{}_{}'.format(rawfile.producer.name, rawfile.name, rawfile.date))
    analysis.save()
    jobutil.create_file_job('run_longit_qc_workflow', storedfile.id,
                               analysis.id, wf_id, dbfn_id)


def set_libraryfile(request):
    if request.method == 'POST':
        try:
            client_id = request.POST['client_id']
            fn_id = request.POST['fn_id']
        except KeyError as error:
            print('POST request to register_file with missing parameter, '
                  '{}'.format(error))
            return HttpResponseForbidden()
        if client_id != settings.ADMIN_APIKEY:
            print('POST request with incorrect client id '
                  '{}'.format(client_id))
            return HttpResponseForbidden()
        try:
            rawfn = RawFile.objects.get(pk=fn_id)
        except RawFile.DoesNotExist:
            print('POST request with incorrect fn id '
                  '{}'.format(fn_id))
            return HttpResponseForbidden()
        else:
            sfile = StoredFile.objects.select_related('servershare').get(
                rawfile_id=fn_id)
            if LibraryFile.objects.filter(sfile__rawfile_id=fn_id):
                pass
            elif sfile.servershare.name == settings.TMPSHARENAME:
                LibraryFile.objects.create(sfile=sfile, 
                                           description=request.POST['desc'])
            else:
                jobutil.create_file_job('move_singlefile', sfile.id)
                LibraryFile.objects.create(sfile=sfile, 
                                           description=request.POST['desc'])
        return HttpResponse()

