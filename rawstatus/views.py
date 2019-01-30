from django.http import (JsonResponse, HttpResponseForbidden,
                         HttpResponse, HttpResponseNotAllowed)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import os
import re
import json
from uuid import uuid4
import requests
from hashlib import md5
from urllib.parse import urlsplit

from kantele import settings
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare,
                              SwestoreBackedupFile, StoredFileType, UserFile,
                              UserFileUpload)
from rawstatus import jobs as rsjobs
from analysis.models import (Analysis, LibraryFile, AnalysisResultFile)
from datasets import views as dsviews
from datasets import models as dsmodels
from dashboard import models as dashmodels
from jobs import jobs as jobutil
from datetime import datetime


def show_files(request):
    files = []
    for sfn in StoredFile.objects.filter(
            filetype=settings.RAW_SFGROUP_ID, checked=False).select_related('rawfile'):
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
            fn, size, md5, filedate_raw = get_registration_postdetails(request.POST)
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
        response = get_or_create_rawfile(md5, fn, producer, size, file_date, request.POST)
        return JsonResponse(response)
    else:
        return HttpResponseNotAllowed(permitted_methods=['POST'])


def get_registration_postdetails(postdata):
    return postdata['fn'], postdata['size'], postdata['md5'], postdata['date'],


@login_required
def request_userupload(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    token = str(uuid4())
    expiry = timezone.now() + timedelta(0.33)  # 8h expiry for big files
    ftype_id = StoredFileType.objects.get(name=request.POST['ftype']).id
    uupload = UserFileUpload(token=token, user=request.user, expires=expiry,
                             filetype_id=ftype_id)
    uupload.save()
    return JsonResponse({'token': token, 'expires': expiry})


def register_userupload(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    try:
        fn, size, md5, filedate_raw = get_registration_postdetails(request.POST)
        desc = request.POST['description']
    except KeyError as error:
        print('POST request to register_file with missing parameter, '
              '{}'.format(error))
        return HttpResponseForbidden()
    try:
        file_date = datetime.strftime(
            datetime.fromtimestamp(float(filedate_raw)), '%Y-%m-%d %H:%M')
    except ValueError as error:
        print('POST request to register_file with incorrect formatted '
              'date parameter {}'.format(error))
        return HttpResponseForbidden()
    producer = Producer.objects.get(shortname='admin')
    try:
        upload = UserFileUpload.objects.get(token=request.POST['token'])
    except (KeyError, UserFileUpload.DoesNotExist):
        return HttpResponseForbidden()
    if UserFile.objects.filter(upload=upload).count():
        print('This token {} is already active for another upload'.format(request.POST['token']))
        return HttpResponseForbidden()
    response = get_or_create_rawfile(md5, fn, producer, size, file_date, {'claimed': True})
    raw = RawFile.objects.get(pk=response['file_id'])
    sfile = StoredFile(rawfile_id=response['file_id'], 
                       filename='userfile_{}_{}'.format(raw.id, raw.name), md5='',
                       checked=False, filetype=upload.filetype,
                       path=settings.UPLOADDIR,
                       servershare=ServerShare.objects.get(name=settings.ANALYSISSHARENAME))
    sfile.save()
    ufile = UserFile(sfile=sfile, description=desc, upload=upload)
    ufile.save()
    return JsonResponse(response)


def get_or_create_rawfile(md5, fn, producer, size, file_date, postdata):
    try:
        existing_fn = RawFile.objects.get(source_md5=md5)
    except RawFile.DoesNotExist:
        claim = 'claimed' in postdata and postdata['claimed']
        file_record = RawFile(name=fn, producer=producer, source_md5=md5,
                              size=size, date=file_date, claimed=claim)
        file_record.save()
        response = {'file_id': file_record.id, 'state': 'registered',
                    'stored': False}
    else:
        stored = True if StoredFile.objects.select_related(
            'rawfile').filter(rawfile__source_md5=md5).count() else False
        msg = ('File {} is already registered and has MD5 {}. It is {}'
               'stored'.format(existing_fn.name, existing_fn.source_md5,
                               '' if stored else 'not '))
        response = {'stored': stored, 'md5': existing_fn.source_md5,
                    'msg': msg}
        response['state'] = 'registered' if stored else 'error'
        if existing_fn.source_md5 == md5:
            response['file_id'] = existing_fn.id
    return response


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
            print('POST request to file_transferred with missing parameter, '
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
            ftypeid = {x.name: x.id for x in StoredFileType.objects.all()}[ftype]
        except KeyError:
            return HttpResponseForbidden('File type does not exist')
        try:
            file_transferred = StoredFile.objects.get(rawfile_id=fn_id,
                                                      filetype_id=ftypeid)
        except StoredFile.DoesNotExist:
            print('New transfer registered, fn_id {}'.format(fn_id))
            file_transferred = StoredFile(rawfile_id=fn_id, filetype_id=ftypeid,
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


def upload_userfile(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    try:
        ufile = UserFile.objects.select_related('sfile__servershare', 'upload').get(
            upload__token=request.POST['token'])
    except (KeyError, UserFileUpload.DoesNotExist) as e:
        print(e)
        return HttpResponseForbidden()
    else:
        if ufile.upload.expires < timezone.now():
            print('expired', ufile.upload.expires)
            return HttpResponseForbidden()
    # FIXME chekc if only one FILE
    dstdir = os.path.join(settings.SHAREMAP[ufile.sfile.servershare.name], ufile.sfile.path) 
    try:
        os.makedirs(dstdir)
    except FileExistsError:
        pass
    except Exception:
        raise
    dst = os.path.join(dstdir, ufile.sfile.filename)
    tmpfp = request.FILES['file']
    with open(dst, 'wb') as fp:
        for chunk in tmpfp.chunks():
            fp.write(chunk)
    jobutil.create_file_job('get_md5', ufile.sfile.id)
    return HttpResponse()


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
    print('Transfer state requested for fn_id {}, type {}'.format(fn_id, ftype))
    try:
        ftypeid = {x.name: x.id for x in StoredFileType.objects.all()}[ftype]
    except KeyError:
        return HttpResponseForbidden('File type does not exist')
    try:
        file_transferred = StoredFile.objects.select_related('rawfile').get(
            rawfile_id=fn_id, filetype_id=ftypeid)
    except StoredFile.DoesNotExist:
        return JsonResponse({'fn_id': fn_id, 'md5_state': False})
    else:
        return do_md5_check(file_transferred)


def check_md5_success_userfile(request):
    if not request.method == 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    try:
        fn_id = request.GET['fn_id']
        token = request.GET['token']
    except KeyError:
        return HttpResponseForbidden()
    try:
        upload = UserFileUpload.objects.get(token=request.GET['token'], finished=False)
    except UserFileUpload.DoesNotExist:
        return HttpResponseForbidden()
    print('Transfer state requested for userfile fn_id {}'.format(fn_id))
    resp = do_md5_check(upload.userfile.sfile)
    if json.loads(resp.content)['md5_state']:
        upload.finished = True
        upload.save()
    return resp


def do_md5_check(file_transferred):
    file_registered = file_transferred.rawfile
    if not file_transferred.md5:
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': False})
    elif file_registered.source_md5 == file_transferred.md5:
        if not file_transferred.checked:
            file_transferred.checked = True
            file_transferred.save()
        if (not AnalysisResultFile.objects.filter(sfile_id=file_transferred) and
                SwestoreBackedupFile.objects.filter(
                storedfile_id=file_transferred.id).count() == 0):
            fn = file_transferred.filename
            if 'QC' in fn and 'hela' in fn.lower() and any([x in fn for x in ['QE', 'HFLu', 'HFLe', 'Velos']]):
                singlefile_qc(file_transferred.rawfile, file_transferred)
            jobutil.create_file_job('create_swestore_backup',
                                    file_transferred.id, file_transferred.md5)
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'error'})


def singlefile_qc(rawfile, storedfile):
    """This method is only run for detecting new incoming QC files"""
    add_to_qc(rawfile, storedfile)
    jobutil.create_file_job('convert_single_mzml', storedfile.id,
                            queue=settings.QUEUE_QCPWIZ)
    start_qc_analysis(rawfile, storedfile, settings.LONGQC_NXF_WF_ID,
                      settings.LONGQC_FADB_ID)


def get_file_owners(sfile):
    owners = {x.id for x in User.objects.filter(is_superuser=True)}
    if hasattr(sfile.rawfile, 'datasetrawfile'):
        owners.add(sfile.rawfile.datasetrawfile.dataset.user.id)
    elif hasattr(sfile, 'analysisresultfile'):
        owners.add(sfile.analysisresultfile.analysis.user.id)
    return owners
 

@login_required
def rename_file(request):
    """Renames a single file. This checks if characters are correct, launches job
    with bare filename (no extension), since job determines if mutliple files including
    mzML have to be renamed."""
    if not request.method == 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    data =  json.loads(request.body.decode('utf-8'))
    try:
        sfile = StoredFile.objects.filter(pk=data['sf_id']).select_related(
            'rawfile').get()
        newfilename = os.path.splitext(data['newname'])[0]
        #mv_mzml = data['mvmzml']  # TODO optional mzml renaming too? Now it is default
    except (StoredFile.DoesNotExist, KeyError):
        print('Stored file to rename does not exist')
        return HttpResponseForbidden()
    if request.user.id not in get_file_owners(sfile):
        print('No ownership of file to rename')
        return HttpResponseForbidden()
    if re.match('^[a-zA-Z_0-9\-]*$', newfilename) is None or sfile.filetype_id in [settings.MZML_SFGROUP_ID, settings.REFINEDMZML_SFGROUP_ID]:
        # TODO Give proper errors to JSON if possible!
        print('Illegal characters in filename {}'.format(newfilename))
        return HttpResponseForbidden()
    jobutil.create_file_job('rename_file', sfile.id, newfilename)



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
    for rawfn, sfn in zip(rawfiles, storedfiles):
        if not dashmodels.QCData.objects.filter(
                analysis__nextflowsearch__nfworkflow=settings.LONGQC_NXF_WF_ID,
                rawfile=rawfn.id).count():
            start_qc_analysis(rawfn, sfn, settings.LONGQC_NXF_WF_ID, settings.LONGQC_FADB_ID)
        else:
            print('QC has already been done with this workflow (id: {}) for '
                  'rawfile id {}'.format(settings.LONGQC_NXF_WF_ID, rawfn.id))


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
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
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
            response = {'library': True, 'state': 'ok'}
        elif sfile.servershare.name == settings.TMPSHARENAME:
            libfn = LibraryFile.objects.create(
                sfile=sfile, description=request.POST['desc'])
            jobutil.create_file_job(
                'move_single_file', sfile.id, settings.LIBRARY_FILE_PATH,
                newname='libfile_{}_{}'.format(libfn.id, sfile.filename))
            response = {'library': True, 'state': 'ok'}
        else:
            LibraryFile.objects.create(sfile=sfile,
                                       description=request.POST['desc'])
            response = {'library': False, 'state': 'ok'}
    return JsonResponse(response)


def check_libraryfile_ready(request):
    if not request.method == 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    try:
        libfn = LibraryFile.objects.select_related('sfile__servershare').get(
            sfile__rawfile_id=request.GET['fn_id'])
    except LibraryFile.DoesNotExist:
        print('request with incorrect fn id '
              '{}'.format(fn_id))
        return HttpResponseForbidden()
    else:
        if libfn.sfile.servershare.name == settings.STORAGESHARENAME and libfn.sfile.path == settings.LIBRARY_FILE_PATH:
            response = {'library': True, 'ready': True, 'state': 'ok'}
        else:
            response = {'library': True, 'ready': False, 'state': 'ok'}
        return JsonResponse(response)


@login_required
def download_px_project(request):
    # FIXME check if pxacc exists on pride and here, before creating dset
    # FIXME View checks project and returns maybe as a nicety how many files it will download.
    # FIXME if already exist, update experiment name in view
    # get or create dataset
    dset = dsviews.get_or_create_px_dset(request.POST['exp'], request.POST['px_acc'], request.POST['user_id'])
    # get or create raw/storedfiles
    date = datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M')
    tmpshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
    raw_ids = []
    extprod = Producer.objects.get(pk=settings.EXTERNAL_PRODUCER_ID)
    for fn in rsjobs.call_proteomexchange(request.POST['px_acc']):
        ftpurl = urlsplit(fn['downloadLink'])
        filename = os.path.split(ftpurl.path)[1]
        fakemd5 = md5()
        fakemd5.update(filename.encode('utf-8'))
        fakemd5 = fakemd5.hexdigest()
        rawfn = get_or_create_rawfile(fakemd5, filename, extprod,
                                      fn['fileSize'], date, {'claimed': True})
        raw_ids.append(rawfn['file_id'])
        if not rawfn['stored']:
            sfn = StoredFile(rawfile_id=rawfn['file_id'], filetype_id=settings.RAW_SFGROUP_ID,
                             servershare=tmpshare, path='',
                             filename=filename, md5='', checked=False)
            sfn.save()
    rsjob = jobutil.create_dataset_job(
        'download_px_data', dset.id, request.POST['px_acc'], raw_ids,
        settings.TMPSHARENAME)
    return HttpResponse()
