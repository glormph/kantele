from django.http import (JsonResponse, HttpResponseForbidden, FileResponse,
                         HttpResponse, HttpResponseNotAllowed)
from django.shortcuts import render
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required

from datetime import timedelta
import os
import re
import json
import shutil
import zipfile
from tempfile import NamedTemporaryFile, mkstemp
from uuid import uuid4
import requests
from hashlib import md5
from urllib.parse import urlsplit
from Bio import SeqIO

from kantele import settings
from rawstatus.models import (RawFile, Producer, StoredFile, ServerShare,
                              SwestoreBackedupFile, StoredFileType, UserFile,
                              PDCBackedupFile, UserFileUpload)
from rawstatus import jobs as rsjobs
from analysis.models import (Analysis, LibraryFile, AnalysisResultFile, NextflowWfVersion)
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
def browser_userupload(request):
    if request.method != 'POST':
        uploadable_filetypes = StoredFileType.objects.filter(name__in=['database'])
        return JsonResponse({'upload_ftypes': {ft.id: ft.filetype for ft in uploadable_filetypes}})
    err_resp = {'error': 'File is not correct FASTA', 'success': False}
    data = request.POST
    # create userfileupload model (incl. fake token)
    try:
        int(data['ftype_id'])
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Please select a file type'})
    token, expiry, upload = store_userfileupload(data['ftype_id'], request.user)
    # tmp write file 
    upfile = request.FILES['file']
    hash = md5()
    producer = Producer.objects.get(shortname='admin')
    desc = data['desc'].strip()
    if desc == '':
        return JsonResponse({'success': False, 'error': 'A description for this file is required'})
    with NamedTemporaryFile(mode='w+') as fp:
        for chunk in upfile.chunks():
            try:
                text = chunk.decode('utf-8')
            except UnicodeDecodeError:
                return JsonResponse(err_resp)
            else:
                fp.write(text)
            hash.update(chunk)
        # check if it is correct FASTA (maybe add more parsing later)
        fp.seek(0)
        if not any(SeqIO.parse(fp, 'fasta')):
            return JsonResponse(err_resp)
        hash = hash.hexdigest() 
        raw = get_or_create_rawfile(hash, upfile.name, producer, upfile.size, timezone.now(), {'claimed': True})
        sfile = StoredFile(rawfile_id=raw['file_id'], 
                       filename='userfile_{}_{}'.format(raw['file_id'], upfile.name), md5=hash,
                       checked=False, filetype=upload.filetype,
                       path=settings.UPLOADDIR,
                       servershare=ServerShare.objects.get(name=settings.ANALYSISSHARENAME))
        sfile.save()
        ufile = UserFile(sfile=sfile, description=desc, upload=upload)
        ufile.save()
        dst = os.path.join(settings.SHAREMAP[sfile.servershare.name], sfile.path,
            sfile.filename)
        shutil.copy(fp.name, dst)
    return JsonResponse({'error': False, 'success': True})

    
@login_required
def request_token_userupload(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    data = json.loads(request.body.decode('utf-8'))
    token, expiry, ufu = store_userfileupload(data['ftype_id'], request.user)
    return JsonResponse({'token': token, 'expires': expiry})


def store_userfileupload(ftype_id, user):
    token = str(uuid4())
    expiry = timezone.now() + timedelta(0.33)  # 8h expiry for big files
    uupload = UserFileUpload(token=token, user=user, expires=expiry, filetype_id=ftype_id)
    uupload.save()
    return token, expiry, uupload


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
            ftype_id = request.POST['ftype_id']
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
            rawfn = RawFile.objects.get(pk=fn_id)
        except RawFile.DoesNotExist:
            print('File has not been registered yet, cannot transfer')
            return JsonResponse({'fn_id': fn_id, 'state': 'error'})
        try:
            ftype_id = StoredFileType.objects.get(pk=ftype_id).id
        except StoredFileType.DoesNotExist:
            return HttpResponseForbidden('File type does not exist')
        try:
            file_transferred = StoredFile.objects.get(rawfile_id=fn_id,
                                                      filetype_id=ftype_id)
        except StoredFile.DoesNotExist:
            print('New transfer registered, fn_id {}'.format(fn_id))
            file_transferred = StoredFile(rawfile_id=fn_id, filetype_id=ftype_id,
                                          servershare=tmpshare, path='',
                                          filename=fname, md5='', checked=False)
            file_transferred.save()
            jobutil.create_job('get_md5', source_md5=rawfn.source_md5, sf_id=file_transferred.id)
        else:
            print('File already registered as transferred, client asks for new '
                  'MD5 check after a possible retransfer. Running MD5 check.')
            jobutil.create_job('get_md5', source_md5=rawfn.source_md5, sf_id=file_transferred.id)
        return JsonResponse({'fn_id': fn_id, 'state': 'ok'})
    else:
        return HttpResponseNotAllowed(permitted_methods=['POST'])


def upload_userfile_token(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    try:
        ufile = UserFile.objects.select_related('sfile__servershare', 'sfile__rawfile', 'upload').get(
            upload__token=request.POST['token'])
    except (KeyError, UserFileUpload.DoesNotExist) as e:
        print(e)
        return HttpResponseForbidden()
    else:
        if ufile.upload.expires < timezone.now():
            print('expired', ufile.upload.expires)
            return HttpResponseForbidden()
    move_uploaded_file(ufile, request.FILES['file'])
    jobutil.create_job('get_md5', source_md5=ufile.sfile.rawfile.source_md5, sf_id=ufile.sfile.id)
    return HttpResponse()


def move_uploaded_file(ufile, tmpfp):
    # FIXME chekc if only one FILE
    dstdir = os.path.join(settings.SHAREMAP[ufile.sfile.servershare.name], ufile.sfile.path) 
    try:
        os.makedirs(dstdir)
    except FileExistsError:
        pass
    except Exception:
        raise
    dst = os.path.join(dstdir, ufile.sfile.filename)
    with open(dst, 'wb') as fp:
        for chunk in tmpfp.chunks():
            fp.write(chunk)


def check_md5_success(request):
    if not request.method == 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    try:
        fn_id = request.GET['fn_id']
        ftype_id = request.GET['ftype_id']
        client_id = request.GET['client_id']
    except KeyError:
        return HttpResponseForbidden()
    try:
        check_producer(client_id)
    except Producer.DoesNotExist:
        return HttpResponseForbidden()
    print('Transfer state requested for fn_id {}, type {}'.format(fn_id, ftype_id))
    try:
        file_transferred = StoredFile.objects.select_related('rawfile__producer__msinstrument__instrumenttype').get(
            rawfile_id=fn_id, filetype_id=ftype_id)
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
        if (not AnalysisResultFile.objects.filter(sfile_id=file_transferred) and not
                PDCBackedupFile.objects.filter(storedfile_id=file_transferred.id):
            fn = file_transferred.filename
            jobutil.create_job('create_pdc_archive', sf_id=file_transferred.id)
            if hasattr(file_registered.producer, 'msinstrument') and file_registered.producer.msinstrument.filetype.is_folder:
                jobutil.create_job('unzip_raw_datadir', sf_id=file_transferred.id)
            if 'QC' in fn and 'hela' in fn.lower() and hasattr(file_registered.producer, 'msinstrument'): 
                singlefile_qc(file_transferred.rawfile, file_transferred)
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'error'})


def singlefile_qc(rawfile, storedfile):
    """This method is only run for detecting new incoming QC files"""
    add_to_qc(rawfile, storedfile)
    filters = ['"peakPicking true 2"', '"precursorRefine"']
    options = []
    if rawfile.producer.msinstrument.instrumenttype.name == 'timstof':
        filters.append('"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"')
        options.append('--combineIonMobilitySpectra')
    params = ['--filters', ';'.join(filters), '--options', ';'.join([x[2:] for x in options])]
    wf_id = NextflowWfVersion.objects.filter(nfworkflow__workflow__shortname__name='QC').latest('pk')
    start_qc_analysis(rawfile, storedfile, wf_id, settings.LONGQC_FADB_ID, params)


def get_file_owners(sfile):
    owners = {x.id for x in User.objects.filter(is_superuser=True)}
    if hasattr(sfile.rawfile, 'datasetrawfile'):
        owners.update(dsviews.get_dataset_owners_ids(sfile.rawfile.datasetrawfile.dataset))
    elif hasattr(sfile, 'analysisresultfile'):
        owners.add(sfile.analysisresultfile.analysis.user.id)
    return owners
 

@login_required
def rename_file(request):
    """Renames a single file. This checks if characters are correct, launches job
    with bare filename (no extension), since job determines if mutliple files including
    mzML have to be renamed."""
    if not request.method == 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    data =  json.loads(request.body.decode('utf-8'))
    try:
        sfile = StoredFile.objects.filter(pk=data['sf_id']).select_related(
            'rawfile').get()
        newfilename = os.path.splitext(data['newname'])[0]
        #mv_mzml = data['mvmzml']  # TODO optional mzml renaming too? Now it is default
    except (StoredFile.DoesNotExist, KeyError):
        print('Stored file to rename does not exist')
        return JsonResponse({'error': 'File does not exist'}, status=403)
    if request.user.id not in get_file_owners(sfile):
        return JsonResponse({'error': 'Not authorized to rename this file'}, status=403)
    elif sfile.filetype_id in [settings.MZML_SFGROUP_ID, settings.REFINEDMZML_SFGROUP_ID]:
        return JsonResponse({'error': 'Files of this type cannot be renamed'}, status=403)
    elif re.match('^[a-zA-Z_0-9\-]*$', newfilename) is None:
        return JsonResponse({'error': 'Illegal characteres in new file name'}, status=403)
    jobutil.create_job('rename_file', sf_id=sfile.id, newname=newfilename)
    return JsonResponse({})


def manyfile_qc(rawfiles, storedfiles):
    """For reanalysis or batching by hand"""
    for rawfn, sfn in zip(rawfiles, storedfiles):
        try:
            dsmodels.DatasetRawFile.objects.select_related(
                'dataset').filter(rawfile=rawfn).get().dataset
        except dsmodels.DatasetRawFile.DoesNotExist:
            dset = add_to_qc(rawfn, sfn)
            print('Added QC file {} to QC dataset {}'.format(rawfn.id, dset.id))
        filters = ['"peakPicking true 2"', '"precursorRefine"']
        options = []
        if rawfn.producer.msinstrument.instrumenttype.name == 'timstof':
            filters.append('"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"')
            options.append('--combineIonMobilitySpectra')
        jobutil.create_job('convert_single_mzml', options=options, filters=filters, sf_id=sfn.id)
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


def start_qc_analysis(rawfile, storedfile, wf_id, dbfn_id, params):
    analysis = Analysis(user_id=settings.QC_USER_ID,
                        name='{}_{}_{}'.format(rawfile.producer.name, rawfile.name, rawfile.date))
    analysis.save()
    jobutil.create_job('run_longit_qc_workflow', sf_id=storedfile.id,
                            analysis_id=analysis.id, wfv_id=wf_id, dbfn_id=dbfn_id,
                            params=params)


def set_libraryfile(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    try:
        client_id = request.POST['client_id']
        fn_id = request.POST['fn_id']
        desc = request.POST['desc']
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
            libfn = LibraryFile.objects.create(sfile=sfile, description=desc)
            jobutil.create_job(
                'move_single_file', sf_id=sfile.id, dst_path=settings.LIBRARY_FILE_PATH,
                newname='libfile_{}_{}'.format(libfn.id, sfile.filename))
            response = {'library': True, 'state': 'ok'}
        else:
            LibraryFile.objects.create(sfile=sfile, description=desc)
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
              '{}'.format(request.GET['fn_id']))
        return HttpResponseForbidden()
    else:
        if libfn.sfile.servershare.name == settings.STORAGESHARENAME and libfn.sfile.path == settings.LIBRARY_FILE_PATH:
            response = {'library': True, 'ready': True, 'state': 'ok'}
        else:
            response = {'library': True, 'ready': False, 'state': 'ok'}
        return JsonResponse(response)


@login_required
@staff_member_required
def instrument_page(request):
    producers = {x.pk: x.name for x in Producer.objects.filter(msinstrument__isnull=False)}
    return render(request, 'rawstatus/instruments.html', {'producers': producers})


@login_required
def download_instrument_package(request):
    datadisk = '{}:'.format(request.POST['datadisk'][0])
    try:
        prod = Producer.objects.select_related('msinstrument').get(pk=request.POST['prod_id'])
    except Producer.DoesNotExist:
        return HttpResponseForbidden()
    runtransferfile = loader.render_to_string('rawstatus/producer.bat', {
        'datadisk': datadisk,
        'client_id': prod.client_id,
        'filetype_id': prod.msinstrument.filetype_id,
        'is_folder': 1 if prod.msinstrument.filetype.is_folder else 0,
        'host': settings.KANTELEHOST,
        'key': settings.TMP_STORAGE_KEYFILE,
        'scp_full': settings.TMP_SCP_PATH,
        })

    if 'configonly' in request.POST and request.POST['configonly'] == 'true':
        resp = HttpResponse(runtransferfile, content_type='application/bat')
        resp['Content-Disposition'] = 'attachment; filename="transfer.bat"'
        return resp
    else:
        # create zip file
        tmpfp, zipfilename = mkstemp()
        shutil.copy('rawstatus/templates/rawstatus/producer.zip', zipfilename)
        with zipfile.ZipFile(zipfilename, 'a') as zipfp:
            zipfp.write('rawstatus/file_inputs/producer.py', 'producer.py')
            zipfp.writestr('transfer.bat', runtransferfile)
        resp = FileResponse(open(zipfilename, 'rb'))
        resp['Content-Disposition'] = 'attachment; filename="{}_filetransfer.zip"'.format(prod.name)
    return resp


def cleanup_old_files(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    try:
        client_id = request.POST['client_id']
    except KeyError as error:
        return HttpResponseForbidden()
    if client_id != settings.ADMIN_APIKEY:
        print('POST request with incorrect client id '
              '{}'.format(client_id))
        return HttpResponseForbidden()
    mzmls = StoredFile.objects.filter(filetype_id__in=settings.SECONDARY_FTYPES)
    maxtime_nonint = timezone.now() - timedelta(settings.MAX_MZML_STORAGE_TIME_POST_ANALYSIS)
    # Filtering gotchas here:
    # filter multiple excludes so they get done in serie, and exclude date__gt rather than
    # filter date__lt because then you get all rows where date is lt, but it does not check
    # if there are ALSO joins where date is gt...
    # old normal mzmls from searches
    old_searched_mzmls = mzmls.exclude(
            rawfile__datasetrawfile__dataset__datatype_id__in=[settings.QC_DATATYPE, settings.LC_DTYPE_ID]).exclude(
            rawfile__datasetrawfile__dataset__datasetsearch__isnull=True).exclude(
            rawfile__datasetrawfile__dataset__datasetsearch__analysis__date__gt=maxtime_nonint)
    # old LC mzmls
    lcmzmls = mzmls.filter(
            rawfile__datasetrawfile__dataset__datatype_id=settings.LC_DTYPE_ID,
            rawfile__datasetrawfile__dataset__datasetsearch__isnull=False).exclude(
            rawfile__datasetrawfile__dataset__datasetsearch__analysis__date__gt=timezone.now() - timedelta(settings.MAX_MZML_LC_STORAGE_TIME))
    # old non-QC mzmls without searches
    old_nonsearched_mzml = mzmls.exclude(
            rawfile__datasetrawfile__dataset__datatype_id=settings.QC_DATATYPE).filter(
            rawfile__datasetrawfile__dataset__datasetsearch__isnull=True,
            regdate__lt=maxtime_nonint)
    # old QC mzml
    qcmzmls = mzmls.filter(rawfile__datasetrawfile__dataset__datatype_id=settings.QC_DATATYPE)
    old_qc_mzmls = qcmzmls.exclude(
            rawfile__storedfile__filejob__job__nextflowsearch__analysis__date__gt=timezone.now() - timedelta(settings.MAX_MZML_QC_STORAGE_TIME))
    # orphan QC mzmls
    nonsearched_qc = qcmzmls.exclude(
            rawfile__storedfile__filejob__job__nextflowsearch__isnull=False).filter(
            regdate__lt=maxtime_nonint)
    all_old_mzmls = old_searched_mzmls.union(lcmzmls, old_nonsearched_mzml, old_qc_mzmls, nonsearched_qc).filter(purged=False)
    # FIXME django 3.0 has iterator(chunk_size=500)
    def chunk_iter(qset, chunk_size):
        chunk = []
        for item in qset.iterator():
            chunk.append(item)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        yield chunk
    for chunk in chunk_iter(all_old_mzmls, 500):
        jobutil.create_job('purge_files', sf_ids=[x.id for x in chunk])
    return HttpResponse()


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
    rsjob = jobutil.create_job(
        'download_px_data', dset_id=dset.id, pxacc=request.POST['px_acc'], rawfnids=raw_ids,
        sharename=settings.TMPSHARENAME)
    return HttpResponse()
