from django.http import (JsonResponse, HttpResponseForbidden, FileResponse,
                         HttpResponse)
from django.shortcuts import render
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q

from datetime import timedelta, datetime
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
                              PDCBackedupFile, UploadToken)
from rawstatus import jobs as rsjobs
from rawstatus.tasks import search_raws_downloaded
from analysis.models import (Analysis, LibraryFile, AnalysisResultFile, NextflowWfVersion)
from datasets import views as dsviews
from datasets import models as dsmodels
from dashboard import models as dashmodels
from jobs import models as jm
from jobs import jobs as jobutil


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

@login_required
@staff_member_required
def import_external_data(request):
    # Input like so: {share_id: int, dirname: top_lvl_dir, dsets: [{'instrument_id': int, 'name': str, 'files': [(path/to/file.raw', ],
    # FIXME thermo files are .raw, but how do we handle bruker raws? they are folders!
    if request.method != 'POST':
         return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    share = ServerShare.objects.get(pk=req['share_id'])
    proj = dsmodels.Project.objects.get(pk=settings.PX_PROJECT_ID)
    exp, created = dsmodels.Experiment.objects.get_or_create(name=req['dirname'], project_id=settings.PX_PROJECT_ID)
    dscreatedata = {'datatype_id': dsviews.get_quantprot_id(), 'prefrac_id': False,
            'ptype_id': settings.LOCAL_PTYPE_ID}
    date = timezone.now()
    for indset in req['dsets']:
        extprod = Producer.objects.get(pk=indset['instrument_id'])
        run, created = dsmodels.RunName.objects.get_or_create(name=indset['name'], experiment=exp)
        dset = dsmodels.Dataset.objects.filter(runname=run)
        if not dset.exists():
            dset = dsviews.save_new_dataset(dscreatedata, proj, exp, run, request.user.id)
        else:
            dset = dset.get()
        raw_ids = []
        for fpath, size in indset['files']:
            path, fn = os.path.split(fpath)
            fakemd5 = md5()
            fakemd5.update(fn.encode('utf-8'))
            fakemd5 = fakemd5.hexdigest()
            rawfn = get_or_create_rawfile(fakemd5, fn, extprod, size, date, {'claimed': True})
            raw_ids.append(rawfn['file_id'])
            if not rawfn['stored']:
                sfn = StoredFile(rawfile_id=rawfn['file_id'],
                        filetype_id=extprod.msinstrument.filetype_id,
                        servershare_id=share.id, path=os.path.join(req['dirname'], path), filename=fn, md5='', checked=False)
                sfn.save()
        # Jobs to get MD5 etc
        jobutil.create_job('register_external_raw', dset_id=dset.id, rawfnids=raw_ids, sharename=share.name)
    return JsonResponse({})


@login_required
@staff_member_required
@require_GET
def scan_raws_tmp(request):
    if 'dirname' not in request.GET:
        return JsonResponse({'shares': [{'id': x.id, 'name': x.name} 
            for x in ServerShare.objects.filter(name='tmp')]})
    dirname = request.GET['dirname']
    serversharename = 'tmp'
    res = search_raws_downloaded.delay(serversharename, dirname)
    # TODO make async to allow large time diff if we have network or other
    # problems, or are busy on backend file server
    exprods = Producer.objects.filter(pk__in=settings.EXTERNAL_PRODUCER_IDS)
    result = res.get()
    return JsonResponse({'dirsfound': result, 'instruments': [(ep.id, ep.name) for ep in exprods]})


@require_POST
def register_file(request):
    """Treats POST requests with:
        - client_id
        - filename
        - md5
        - date of production/acquisition
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        token = data['token']
    except json.decoder.JSONDecodeError:
        data = request.POST
        token = False
    try:
        client_id = data['client_id']
        fn, size, md5, filedate_raw = get_registration_postdetails(data)
    except KeyError as error:
        print('POST request to register_file with missing parameter, '
              '{}'.format(error))
        return JsonResponse({'error': 'Data load for URL incorrect'}, status=403)
    producer, upload = get_producer_and_userupload(client_id, token)
    if not any([producer, upload]):
        return JsonResponse({'error': 'Could not verify access'}, status=403)
    elif upload:
        # Upload contains producer, generated when requesting an upload token
        producer = upload.producer
    try:
        file_date = datetime.strftime(
            datetime.fromtimestamp(float(filedate_raw)), '%Y-%m-%d %H:%M')
    except ValueError as error:
        print('POST request to register_file with incorrect formatted '
              'date parameter {}'.format(error))
        return JsonResponse({'error': 'Data load for URL incorrect'}, status=403)
    response = get_or_create_rawfile(md5, fn, producer, size, file_date, data)
    return JsonResponse(response)


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
    dighash = md5()
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
            dighash.update(chunk)
        # check if it is correct FASTA (maybe add more parsing later)
        fp.seek(0)
        if not any(SeqIO.parse(fp, 'fasta')):
            return JsonResponse(err_resp)
        dighash = dighash.hexdigest() 
        raw = get_or_create_rawfile(dighash, upfile.name, producer, upfile.size, timezone.now(), {'claimed': True})
        # never check browser-userfiles, MD5 is checked on delivery so, just assume checked = True
        sfile = StoredFile.objects.create(rawfile_id=raw['file_id'],
                       filename='userfile_{}_{}'.format(raw['file_id'], upfile.name), md5=dighash,
                       checked=True, filetype=upload.filetype,
                       path=settings.UPLOADDIR,
                       servershare=ServerShare.objects.get(name=settings.ANALYSISSHARENAME))
        ufile = UserFile(sfile=sfile, description=desc, upload=upload)
        ufile.save()
        dst = os.path.join(settings.SHAREMAP[sfile.servershare.name], sfile.path,
            sfile.filename)
        shutil.copy(fp.name, dst)
    return JsonResponse({'error': False, 'success': True})

    
# TODO view for asking tokens or put it in the fasta upload view


@login_required
@require_POST
def request_token_userupload(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        producer = Producer.objects.get(pk=data['producer_id'])
    except Producer.DoesNotExist:
        return JsonResponse({'error': True, 'error': 'Cannot use that file producer'}, status=403)
    if producer.internal:
        return JsonResponse({'error': True, 'error': 'Cannot use internal file producer for own uploads'}, status=403)
    else:
        ufu = store_userfileupload(data['ftype_id'], request.user, producer)
        # token_ft_host_b64 = b64encode('|'.join([ufu.token, settings.KANTELEHOST]).encode('utf-8'))
        return JsonResponse({'token': ufu.token, #token_ft_host_b64.decode('utf-8'),
            'expires': ufu.expires})


def store_userfileupload(ftype_id, user, producer):
    token = str(uuid4())
    expiry = timezone.now() + timedelta(0.33)  # 8h expiry for big files
    uupload = UploadToken.objects.create(token=token, user=user, expired=False,
            expires=expiry, filetype_id=ftype_id, producer=producer)
    return uupload


@require_POST
def register_public_key_tmp_upload(request):
    # FIXME
    data = json.loads(request.body.decode('utf-8'))
#    try:
#        check_token

#@require_POST
#def register_userupload(request):
#    try:
#        fn, size, md5, filedate_raw = get_registration_postdetails(request.POST)
#        desc = request.POST['description']
#    except KeyError as error:
#        print('POST request to register_file with missing parameter, '
#              '{}'.format(error))
#        return HttpResponseForbidden()
#    try:
#        file_date = datetime.strftime(
#            datetime.fromtimestamp(float(filedate_raw)), '%Y-%m-%d %H:%M')
#    except ValueError as error:
#        print('POST request to register_file with incorrect formatted '
#              'date parameter {}'.format(error))
#        return HttpResponseForbidden()
#    producer = Producer.objects.get(shortname='admin')
#    try:
#        upload = UserFileUpload.objects.get(token=request.POST['token'])
#    except (KeyError, UserFileUpload.DoesNotExist):
#        return HttpResponseForbidden()
#    if UserFile.objects.filter(upload=upload).count():
#        print('This token {} is already active for another upload'.format(request.POST['token']))
#        return HttpResponseForbidden()
#    response = get_or_create_rawfile(md5, fn, producer, size, file_date, {'claimed': True})
#    raw = RawFile.objects.get(pk=response['file_id'])
#    sfile = StoredFile.objects.create(rawfile_id=response['file_id'], 
#                       filename='userfile_{}_{}'.format(raw.id, raw.name), md5=md5,
#                       checked=False, filetype=upload.filetype,
#                       path=settings.UPLOADDIR,
#                       servershare=ServerShare.objects.get(name=settings.ANALYSISSHARENAME))
#    ufile = UserFile(sfile=sfile, description=desc, upload=upload)
#    ufile.save()
#    return JsonResponse(response)


def get_or_create_rawfile(md5, fn, producer, size, file_date, postdata):
    rawfn, created = RawFile.objects.get_or_create(source_md5=md5, defaults={
        'name': fn, 'producer': producer, 'size': size, 'date': file_date,
        'claimed': postdata.get('claimed', False)})
    if not created:
        nrsfn = StoredFile.objects.filter(md5=md5, checked=True).count()
        stored = True if nrsfn else False
        state = 'registered' if nrsfn else 'error'
        msg = (f'File {rawfn.name} is already registered and has MD5 '
                '{rawfn.source_md5}. Already stored = {stored}')
    else:
        stored, state, msg = False, 'registered', False
    response = {'file_id': rawfn.id, 'state': state, 'stored': stored, 
            'remote_name': rawfn.name, 'msg': msg}
    return response


def get_producer_and_userupload(client_id, token):
    # FIXME need to remove client_id and only go with token
    producer, upload = False, False
    if client_id:
        try:
            producer = check_producer(client_id)
        except Producer.DoesNotExist:
            print('POST request with incorrect client id '
                  '{}'.format(client_id))
    elif token:
        try:
            upload = UploadToken.objects.get(token=token)
        except UploadToken.DoesNotExist as e:
            print('Token for user upload does not exist')
            pass
        else:
            if upload.expires < timezone.now():
                upload = False
                print('Token expired')
    return producer, upload


# /files/transferstate
# FIXME move to libfile path POST ok tfstate
def get_files_transferstate(request):
    if not request.method == 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    data =  json.loads(request.body.decode('utf-8'))
    # FIXME remove after full transition
    try:
        token = data['token']
    except KeyError:
        token = False
    try:
        fnid = data['fnid']
        client_id = data['client_id']
    except KeyError as error:
        print('Request to get transferstate with missing parameter, '
              '{}'.format(error))
        return JsonResponse({'error': 'Bad request'}, status=400)

    producer, upload = get_producer_and_userupload(client_id, token)
    if not any([producer, upload]):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    # Also do registration here? if MD5? prob not.
    rfn = RawFile.objects.filter(pk=fnid)
    if not rfn.count():
        return JsonResponse({'error': 'File with ID {} cannot be found in system'.format(fnid)}, status=404)
    rfn = rfn.get()
    if producer and rfn.producer != producer:
        # In case the file has been moved to another instrument or the instrument API key
        # is wrong here (unlikely right?)
        return JsonResponse({'error': 'File with ID {} is not from producer {}'.format(rfn.id, producer.name)}, status=403)
    # FIXME if really bad timing, there will be multiple sfns
    # FIXME filetype here, so we can find files derived from rawfile, eg mzML
    # but since mzML also is filetype raw we should be able to use filetype on raw
    if 'ftype_id' in data:
        sfns = rfn.storedfile_set.filter(filetype_id=data['ftype_id'])
    elif upload:
        sfns = rfn.storedfile_set.filter(filetype=upload.filetype)
    else:
        # Only get the files which are not derived for uploads
        sfns = rfn.storedfile_set.filter(mzmlfile__isnull=True)
    if not sfns.count():
        # has not been reported as transferred,
        tstate = 'transfer'
    elif sfns.count() > 1:
        # Now behaviour specifies there can only be one copy of a raw file
        # What happens if there is a copy e.g. on a different server?
        return JsonResponse({'error': 'Problem, there are multiple stored files with that raw file ID'}, status=409)
    else:
        # need to unzip, then MD5 check, then backup
        sfn = sfns.select_related('filetype', 'userfile', 'libraryfile').get()
        if sfn.checked:
            # File transfer and check finished
            tstate = 'done'
            if (not AnalysisResultFile.objects.filter(sfile_id=sfn) and not
                    PDCBackedupFile.objects.filter(storedfile_id=sfn.id)):
                # No analysis result or PDC file, then do some processing work
                process_file_confirmed_ready(rfn, sfn)
        # FIXME this is too hardcoded data model which will be changed one day,
        # needs to be in Job class abstraction!

        elif jm.Job.objects.filter(Q(funcname='get_md5') | Q(funcname='unzip_raw_datadir_md5check'),
                kwargs={'sf_id': sfn.pk, 'source_md5': rfn.source_md5}).exclude(
                state__in=jobutil.JOBSTATES_DONE):
            # this did not work when doing filejob_set.filter ?
            # A second call to this route would fire the md5 again,
            # until the file was checked. But in theory it'd work, and by hand too.
            # Maybe a DB or cache thing, however 3seconds between calls should be enough?
            # Maybe NGINX caches stuff, add some sort of no-cache into the header of request in client producer.py
            # auto update producer would be nice, when it calls server at intervals, then downloads_automaticlly
            # a new version of itself?

            # File not checked, so either md5 check in progress, or it crashed
            tstate = 'wait'

        elif sfn.md5 != rfn.source_md5:
            # MD5 on disk is not same as registered MD5, corrupted transfer
            # reset MD5 on stored file to make sure no NEW stored files are created
            # basically setting its state to pre-transfer state
            sfn.md5 = rfn.source_md5
            sfn.save()
            tstate = 'transfer'

        else:
            # No MD5 job exists for file, fire one, do not report back. Unlikely to happen often
            # since MD5 is checked in transferred-view
            if sfn.filetype.is_folder:
                jobutil.create_job('unzip_raw_datadir_md5check', source_md5=rfn.source_md5, sf_id=sfn.id)
            else:
                jobutil.create_job('get_md5', source_md5=rfn.source_md5, sf_id=sfn.id)
            tstate = 'wait'
    response = {'transferstate': tstate}
    if tstate == 'transfer':
        tmpshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
        response['scp'] = f'{settings.STORAGE_USER}@{tmpshare.uri}:{tmpshare.share}'
    return JsonResponse(response)


def process_file_confirmed_ready(rfn, sfn):
    """Processing of unzip, backup, QC after transfer has succeeded (MD5 checked)
    for newly arrived MS other raw data files (not for analysis etc)"""
    ftype_isdir = hasattr(rfn.producer, 'msinstrument') and rfn.producer.msinstrument.filetype.is_folder
    jobutil.create_job('create_pdc_archive', sf_id=sfn.id, isdir=ftype_isdir)
    fn = sfn.filename
    if 'QC' in fn and 'hela' in fn.lower() and not 'DIA' in fn and hasattr(rfn.producer, 'msinstrument'): 
        singlefile_qc(sfn.rawfile, sfn)
    elif hasattr(sfn, 'libraryfile'):
        jobutil.create_job('move_single_file', sf_id=sfn.id, dst_path=settings.LIBRARY_FILE_PATH,
                newname='libfile_{}_{}'.format(sfn.libraryfile.id, sfn.filename))
    elif hasattr(sfn, 'userfile'):
        jobutil.create_job('move_single_file', sf_id=sfn.id, dst_path=settings.UPLOADDIR,
                newname='userfile_{}_{}'.format(rfn.id, sfn.filename))


@require_POST
def file_transferred(request):
    """Treats POST requests with:
        - fn_id
    Starts checking file MD5 in background
    """
    # FIXME remove this after we've gone to full JSON also in producer instruments
    try:
        data = json.loads(request.body.decode('utf-8'))
        token = data['token']
        libdesc, userdesc = data['libdesc'], data['userdesc']
    except json.decoder.JSONDecodeError:
        data = request.POST
        token = False
        libdesc, userdesc = False, False
    try:
        fn_id = data['fn_id']
        client_id = data['client_id']
        fname = data['filename']
    except KeyError as error:
        print('POST request to file_transferred with missing parameter, '
              '{}'.format(error))
        print(1)
        return JsonResponse({'error': 'Bad request'}, status=400)
    producer, upload = get_producer_and_userupload(client_id, token)
    if not any([producer, upload]):
        return JsonResponse({'error': 'Could not verify access'}, status=403)
    # FIXME only uploadtoken.filetype_id after fixing producer instruments
    ftype_id = data['ftype_id'] if producer else upload.filetype_id
    if not any([producer, upload]):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    tmpshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
    try:
        rawfn = RawFile.objects.get(pk=fn_id)
    except RawFile.DoesNotExist:
        errmsg = 'File with ID {} has not been registered yet, cannot transfer'.format(fn_id)
        print(errmsg)
        return JsonResponse({'state': 'error', 'problem': 'NOT_REGISTERED', 'error': errmsg}, status=403)
    try:
        ftype_id = StoredFileType.objects.get(pk=ftype_id).id
    except StoredFileType.DoesNotExist:
        return JsonResponse({'error': 'File type does not exist'}, status=400)
    file_trf, created = StoredFile.objects.get_or_create(
            rawfile=rawfn, filetype_id=ftype_id,
            md5=rawfn.source_md5,
            defaults={'servershare': tmpshare, 'path': '',
                'filename': fname, 'checked': False})
    if not created:
        print('File already registered as transferred, rerunning MD5 check in case new '
                'file arrived')
        file_trf.checked = False
        file_trf.save()
    elif token and libdesc:
        LibraryFile.objects.create(sfile=file_trf, description=libdesc)
    elif token and userdesc:
        # TODO, external producer, actual raw data, otherwise userfile with description
        UserFile.objects.create(sfile=file_trf, description=userdesc, upload=upload)
    # if re-transfer happens and second time it is corrupt, overwriting old file
    # then we have a problem! So always fire MD5 job, not only on new files
    if file_trf.filetype.is_folder:
        jobutil.create_job('unzip_raw_datadir_md5check', source_md5=rawfn.source_md5, sf_id=file_trf.id)
    else:
        jobutil.create_job('get_md5', source_md5=rawfn.source_md5, sf_id=file_trf.id)
    return JsonResponse({'fn_id': fn_id, 'state': 'ok'})


#@require_POST
#def upload_userfile_token(request):
#    try:
#        ufile = UserFile.objects.select_related('sfile__servershare', 'sfile__rawfile', 'upload').get(
#            upload__token=request.POST['token'])
#    except (KeyError, UserFileUpload.DoesNotExist) as e:
#        print(e)
#        return HttpResponseForbidden()
#    else:
#        if ufile.upload.expires < timezone.now():
#            print('expired', ufile.upload.expires)
#            return HttpResponseForbidden()
#    move_uploaded_file(ufile, request.FILES['file'])
#    jobutil.create_job('get_md5', source_md5=ufile.sfile.rawfile.source_md5, sf_id=ufile.sfile.id)
#    return HttpResponse()


#def move_uploaded_file(ufile, tmpfp):
#    # FIXME chekc if only one FILE
#    dstdir = os.path.join(settings.SHAREMAP[ufile.sfile.servershare.name], ufile.sfile.path) 
#    try:
#        os.makedirs(dstdir)
#    except FileExistsError:
#        pass
#    except Exception:
#        raise
#    dst = os.path.join(dstdir, ufile.sfile.filename)
#    with open(dst, 'wb') as fp:
#        for chunk in tmpfp.chunks():
#            fp.write(chunk)
#

## FIXME deprecate, is now get_trf_state
## just fix in upload  libfiles
#@require_GET
#def check_md5_success(request):
#    try:
#        fn_id = request.GET['fn_id']
#        ftype_id = request.GET['ftype_id']
#        client_id = request.GET['client_id']
#    except KeyError:
#        return HttpResponseForbidden()
#    try:
#        check_producer(client_id)
#    except Producer.DoesNotExist:
#        return HttpResponseForbidden()
#    print('Transfer state requested for fn_id {}, type {}'.format(fn_id, ftype_id))
#    sfiles = StoredFile.objects.select_related('rawfile__producer__msinstrument__instrumenttype').filter(
#            rawfile_id=fn_id, filetype_id=ftype_id)
#    if not sfiles.count():
#        return JsonResponse({'fn_id': fn_id, 'md5_state': False})
#    else:
#        file_transferred = sfiles.get(mzmlfile__isnull=True)
#        return do_md5_check(file_transferred)


## FIXME deprecate, is now get_trf_state
## just fix in upload  libfiles
#@require_GET
#def check_md5_success_userfile(request):
#    try:
#        fn_id = request.GET['fn_id']
#        token = request.GET['token']
#    except KeyError:
#        return HttpResponseForbidden()
#    try:
#        upload = UserFileUpload.objects.get(token=request.GET['token'], finished=False)
#    except UserFileUpload.DoesNotExist:
#        return HttpResponseForbidden()
#    print('Transfer state requested for userfile fn_id {}'.format(fn_id))
#    resp = do_md5_check(upload.userfile.sfile)
#    if json.loads(resp.content)['md5_state']:
#        upload.finished = True
#        upload.save()
#    return resp


def do_md5_check(file_transferred):
    file_registered = file_transferred.rawfile
    if not file_transferred.md5:
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': False})
    elif file_registered.source_md5 == file_transferred.md5:
        if not file_transferred.checked:
            file_transferred.checked = True
            file_transferred.save()
        if (not AnalysisResultFile.objects.filter(sfile_id=file_transferred) and not
                PDCBackedupFile.objects.filter(storedfile_id=file_transferred.id)):
            # Backup after transfer has succeeded (MD5 checked)
            if hasattr(file_registered.producer, 'msinstrument') and file_registered.producer.msinstrument.filetype.is_folder:
                jobutil.create_job('unzip_raw_datadir', sf_id=file_transferred.id)
                ftype_isdir = True
            else:
                ftype_isdir = False
            jobutil.create_job('create_pdc_archive', sf_id=file_transferred.id, isdir=ftype_isdir)
            fn = file_transferred.filename
            if 'QC' in fn and 'hela' in fn.lower() and not 'DIA' in fn and hasattr(file_registered.producer, 'msinstrument'): 
                singlefile_qc(file_transferred.rawfile, file_transferred)
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'ok'})
    else:
        return JsonResponse({'fn_id': file_registered.id, 'md5_state': 'error'})


def singlefile_qc(rawfile, storedfile):
    """This method is only run for detecting new incoming QC files"""
    add_to_qc(rawfile, storedfile)
    filters = ['"peakPicking true 2"', '"precursorRefine"']
    params, options = [], []
    if rawfile.producer.msinstrument.instrumenttype.name == 'timstof':
        filters.append('"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"')
        options.append('--combineIonMobilitySpectra')
        # FIXME until dinosaur can do MS1 on TIMS spectra we have to specify noquant, remove later I hope
        params.append('--noquant')
    if len(filters):
        params.extend(['--filters', ';'.join(filters)])
    if len(options):
        params.extend(['--options', ';'.join([x[2:] for x in options])])
    wf_id = NextflowWfVersion.objects.filter(nfworkflow__workflow__shortname__name='QC').latest('pk').id
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
            'rawfile', 'mzmlfile').get()
        newfilename = os.path.splitext(data['newname'])[0]
        #mv_mzml = data['mvmzml']  # TODO optional mzml renaming too? Now it is default
    except (StoredFile.DoesNotExist, KeyError):
        print('Stored file to rename does not exist')
        return JsonResponse({'error': 'File does not exist'}, status=403)
    if request.user.id not in get_file_owners(sfile):
        return JsonResponse({'error': 'Not authorized to rename this file'}, status=403)
    elif hasattr(sfile, 'mzmlfile'):
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


#@require_POST
#def set_libraryfile(request):
#    '''Transforms a file into a library file and queues job to move it
#    to library location (from e.g. tmp location)'''
#    try:
#        client_id = request.POST['client_id']
#        fn_id = request.POST['fn_id']
#        desc = request.POST['desc']
#    except KeyError as error:
#        print('POST request to register_file with missing parameter, '
#              '{}'.format(error))
#        return HttpResponseForbidden()
#    if client_id != settings.ADMIN_APIKEY:
#        print('POST request with incorrect client id '
#              '{}'.format(client_id))
#        return HttpResponseForbidden()
#    try:
#        rawfn = RawFile.objects.get(pk=fn_id)
#    except RawFile.DoesNotExist:
#        print('POST request with incorrect fn id '
#              '{}'.format(fn_id))
#        return HttpResponseForbidden()
#    else:
#        sfile = StoredFile.objects.select_related('servershare').get(
#            rawfile_id=fn_id)
#        if LibraryFile.objects.filter(sfile__rawfile_id=fn_id):
#            response = {'library': True, 'state': 'ok'}
#        elif sfile.servershare.name == settings.TMPSHARENAME:
#            libfn = LibraryFile.objects.create(sfile=sfile, description=desc)
#            jobutil.create_job(
#                'move_single_file', sf_id=sfile.id, dst_path=settings.LIBRARY_FILE_PATH,
#                newname='libfile_{}_{}'.format(libfn.id, sfile.filename))
#            response = {'library': True, 'state': 'ok'}
#        else:
#            LibraryFile.objects.create(sfile=sfile, description=desc)
#            response = {'library': False, 'state': 'ok'}
#    return JsonResponse(response)
#
#
#@require_GET
#def check_libraryfile_ready(request):
#    '''Checks if libfile has been transferred to library location by a job'''
#    try:
#        libfn = LibraryFile.objects.select_related('sfile__servershare').get(
#            sfile__rawfile_id=request.GET['fn_id'])
#    except LibraryFile.DoesNotExist:
#        print('request with incorrect fn id '
#              '{}'.format(request.GET['fn_id']))
#        return HttpResponseForbidden()
#    else:
#        if libfn.sfile.servershare.name == settings.STORAGESHARENAME and libfn.sfile.path == settings.LIBRARY_FILE_PATH:
#            response = {'library': True, 'ready': True, 'state': 'ok'}
#        else:
#            response = {'library': True, 'ready': False, 'state': 'ok'}
#        return JsonResponse(response)
#

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
    
    transferbat = loader.render_to_string('rawstatus/producer.bat', {'client_id': prod.client_id})
    runtransferfile = json.dumps({
        'outbox': f'{datadisk}\outbox',
        'zipbox': f'{datadisk}\zipbox',
        'donebox': f'{datadisk}\donebox',
        'client_id': prod.client_id,
        'filetype_id': prod.msinstrument.filetype_id,
        'is_folder': 1 if prod.msinstrument.filetype.is_folder else 0,
        'host': settings.KANTELEHOST,
        'key': settings.TMP_STORAGE_KEYFILE,
        'scp_full': settings.TMP_SCP_PATH,
        'producerhostname': prod.name,
        'md5_stable_fns': settings.MD5_STABLE_FILES,
        })

    if 'configonly' in request.POST and request.POST['configonly'] == 'true':
        resp = HttpResponse(runtransferfile, content_type='application/json')
        resp['Content-Disposition'] = 'attachment; filename="transfer_config.json"'
        return resp
    else:
        # create zip file
        tmpfp, zipfilename = mkstemp()
        shutil.copy('rawstatus/templates/rawstatus/producer.zip', zipfilename)
        with zipfile.ZipFile(zipfilename, 'a') as zipfp:
            zipfp.write('rawstatus/file_inputs/producer.py', 'producer.py')
            zipfp.writestr('transfer.bat', transferbat)
            zipfp.writestr('transfer_config.json', runtransferfile)
        resp = FileResponse(open(zipfilename, 'rb'))
        resp['Content-Disposition'] = 'attachment; filename="{}_filetransfer.zip"'.format(prod.name)
    return resp


def getxbytes(bytes, op=50):
    if bytes is None:
        return '0B'
    if bytes >> op:
        return '{}{}B'.format(bytes >> op, {0: '', 10: 'K', 20: 'M', 30: 'G', 40: 'T', 50: 'P'}[op])
    else:
        return getxbytes(bytes, op-10)


@login_required
@require_POST
def cleanup_old_files(request):
    if not request.user.is_staff:
        return JsonResponse({'state': 'error', 'error': 'User has no permission to retire this project, does not own all datasets in project'}, status=403)
    data = json.loads(request.body.decode('utf-8'))
    try:
        queue_job = data['queue_job']
    except KeyError as error:
        return HttpResponseForbidden()
    mzmls = StoredFile.objects.filter(mzmlfile__isnull=False, purged=False)
    maxtime_nonint = timezone.now() - timedelta(settings.MAX_MZML_STORAGE_TIME_POST_ANALYSIS)
    # Filtering gotchas here:
    # filter multiple excludes so they get done in serie, and exclude date__gt rather than
    # filter date__lt because then you get all rows where date is lt, but it does not check
    # if there are ALSO joins where date is gt...
    # old normal mzmls from searches
    old_searched_mzmls = mzmls.exclude(
            rawfile__datasetrawfile__dataset__datatype_id__in=[settings.QC_DATATYPE, *settings.LC_DTYPE_IDS]).exclude(
            rawfile__datasetrawfile__dataset__datasetsearch__isnull=True).exclude(
            rawfile__datasetrawfile__dataset__datasetsearch__analysis__date__gt=maxtime_nonint)
    # old LC mzmls
    lcmzmls = mzmls.filter(
            rawfile__datasetrawfile__dataset__datatype_id__in=settings.LC_DTYPE_IDS,
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
    all_old_mzmls = old_searched_mzmls.union(lcmzmls, old_nonsearched_mzml, old_qc_mzmls, nonsearched_qc)

    def chunk_iter(qset, chunk_size):
        chunk = []
        # Django iterator has chunk_size but that only affects the database caching level
        # and not the chunked output. Here we use this to output chunks to create jobs from
        # otherwise the job params become very large
        for item in qset.iterator():
            chunk.append(item)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        yield chunk

    if queue_job:
        for chunk in chunk_iter(all_old_mzmls, 500):
            jobutil.create_job('purge_files', sf_ids=[x.id for x in chunk])
        return JsonResponse({'ok': True})
    else:
        # cannot aggregate Sum on UNION
        totalsize_raw = getxbytes(sum((x['rawfile__size'] for x in all_old_mzmls.values('rawfile__size'))))
        return JsonResponse({'ok': True, 'mzml_cleanupsize_raws': totalsize_raw})


@login_required
def download_px_project(request):
    # FIXME check if pxacc exists on pride and here, before creating dset
    # FIXME View checks project and returns maybe as a nicety how many files it will download.
    # FIXME if already exist, update experiment name in view
    try:
        expname = request.POST['exp']
        pxacc = request.POST['px_acc']
    except KeyError:
        return JsonResponse({'error': 'Invalid request'}, status=403)
    # First check if we can get the dataset from PX at all
    try:
        px_files = rsjobs.call_proteomexchange(pxacc)
    except RuntimeError as error:
        return JsonResponse({'error': error}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Could not connect to ProteomeXchange server, timed out'}, status=500)

    # Now go through the files
    date = datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M')
    tmpshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
    dset = dsviews.get_or_create_px_dset(expname, pxacc, request.POST['user_id'])
    raw_ids, shasums = [], {}
    extproducers = {x.msinstrument.instrumenttype.name: x for x in Producer.objects.filter(name__startswith='External')}
    for fn in px_files:
        ftpurl = urlsplit(fn['downloadLink'])
        filename = os.path.split(ftpurl.path)[1]
        fakemd5 = md5()
        fakemd5.update(filename.encode('utf-8'))
        fakemd5 = fakemd5.hexdigest()
        rawfn = get_or_create_rawfile(fakemd5, filename, extproducers[fn['instr_type']],
                                       fn['fileSize'], date, {'claimed': True})
        shasums[rawfn['file_id']] = fn['sha1sum']
        if not rawfn['stored']:
            ftid = StoredFileType.objects.get(name='thermo_raw_file', filetype='raw').id
            sfn = StoredFile(rawfile_id=rawfn['file_id'], filetype_id=ftid,
                             servershare=tmpshare, path='',
                             filename=filename, md5='', checked=False)
            sfn.save()
    rsjob = jobutil.create_job(
        'download_px_data', dset_id=dset.id, pxacc=request.POST['px_acc'], sharename=settings.TMPSHARENAME, shasums=shasums)
    return HttpResponse()


@login_required
@require_POST
def restore_file_from_cold(request):
    '''Single file function for restoring archived files, for cases where files are not in dataset,
    e.g. on tmp storage only'''
    data = json.loads(request.body.decode('utf-8'))
    try:
        sfile = StoredFile.objects.select_related('rawfile__datasetrawfile', 'mzmlfile', 'pdcbackedupfile').get(pk=data['item_id'])
    except StoredFile.DoesNotExist:
        return JsonResponse({'error': 'File does not exist'}, status=403)
    if not sfile.purged or not sfile.deleted:
        return JsonResponse({'error': 'File is not currently marked as deleted, will not undelete'}, status=403)
    elif hasattr(sfile.rawfile, 'datasetrawfile'):
        return JsonResponse({'error': 'File is in a dataset, please restore entire set'}, status=403)
    elif not hasattr(sfile, 'pdcbackedupfile'):
        return JsonResponse({'error': 'File has no archived copy in PDC backup registered in Kantele, can not restore'}, status=403)
    elif not sfile.pdcbackedupfile.success or sfile.pdcbackedupfile.deleted:
        return JsonResponse({'error': 'Archived copy exists but cannot be restored from, check with admin'}, status=403)
    elif hasattr(sfile, 'mzmlfile'):
        return JsonResponse({'error': 'mzML derived files are not archived, please regenerate it from RAW data'}, status=403)
    # File is set to deleted, purged = False, False in the post-job-view
    jobutil.create_job('restore_from_pdc_archive', sf_id=sfile.pk)
    return JsonResponse({'state': 'ok'})


@login_required
@require_POST
def archive_file(request):
    '''Single file function for archiving files, for cases where files are not in dataset,
    e.g. on tmp storage only'''
    data = json.loads(request.body.decode('utf-8'))
    try:
        sfile = StoredFile.objects.select_related('rawfile__datasetrawfile', 'filetype', 'rawfile__producer').get(pk=data['item_id'])
    except StoredFile.DoesNotExist:
        return JsonResponse({'error': 'File does not exist'}, status=404)
    except KeyError:
        return JsonResponse({'error': 'Bad request'}, status=400)
    if sfile.purged or sfile.deleted:
        return JsonResponse({'error': 'File is currently marked as deleted, can not archive'}, status=403)
    elif sfile.rawfile.producer.client_id in [settings.ANALYSISCLIENT_APIKEY]:
        return JsonResponse({'error': 'Analysis result files are not archived, they can be regenerated from RAW data'}, status=403)
    elif sfile.rawfile.claimed or hasattr(sfile.rawfile, 'datasetrawfile'):
        return JsonResponse({'error': 'File is in a dataset, please archive entire set or remove it from dataset first'}, status=403)
    elif hasattr(sfile, 'pdcbackedupfile') and sfile.pdcbackedupfile.success == True and sfile.pdcbackedupfile.deleted == False:
        return JsonResponse({'error': 'File is already archived'}, status=403)
    elif hasattr(sfile, 'mzmlfile'):
        return JsonResponse({'error': 'Derived mzML files are not archived, they can be regenerated from RAW data'}, status=403)
    # File is set to deleted,purged=True,True in the post-job-view
    jobutil.create_job('create_pdc_archive', sf_id=sfile.pk, isdir=sfile.filetype.is_folder)
    return JsonResponse({'state': 'ok'})
