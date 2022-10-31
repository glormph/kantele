from django.http import (JsonResponse, HttpResponseForbidden, FileResponse,
                         HttpResponse)
from django.shortcuts import render
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required

from datetime import timedelta, datetime
from functools import wraps
import os
import re
import json
import shutil
import zipfile
from tempfile import NamedTemporaryFile, mkstemp
from uuid import uuid4
from base64 import b64encode
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


#def show_files(request):
#    files = []
#    for sfn in StoredFile.objects.filter(
#            filetype=settings.RAW_SFGROUP_ID, checked=False).select_related('rawfile'):
#        fn = sfn.rawfile
#        files.append({'name': fn.name, 'prod': fn.producer.name,
#                      'date': fn.date, 'backup': False,
#                      'size': round(fn.size / (2**20), 1), 'transfer': False})
#    for sfn in SwestoreBackedupFile.objects.select_related(
#            'storedfile__rawfile').filter(success=False):
#        fn  = sfn.storedfile.rawfile
#        files.append({'name': fn.name, 'prod': fn.producer.name, 'date': fn.date,
#                      'size': round(fn.size / (2**20), 1), 'backup': False,
#                      'transfer': sfn.storedfile.checked})
#    for sfn in SwestoreBackedupFile.objects.order_by(
#            'storedfile__rawfile__date').select_related(
#            'storedfile__rawfile').filter(success=True).exclude(
#            storedfile__checked=False).reverse()[:100]:
#        fn  = sfn.storedfile.rawfile
#        files.append({'name': fn.name, 'prod': fn.producer.name, 'date': fn.date,
#                      'size': round(fn.size / (2**20), 1), 'backup': True,
#                      'transfer': True})
#    return render(request, 'rawstatus/files.html', {'files': files})
#
def inflow_page(request):
    return render(request, 'rawstatus/inflow.html', {
        'producers': {x.id: x.name for x in Producer.objects.filter(msinstrument__active=True,
            internal=True)}, 'filetypes': [{'id': x.id, 'name': x.name, 'israw': x.is_rawdata,
                'isfolder': x.is_folder} for x in StoredFileType.objects.filter(user_uploadable=True)]})


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
                StoredFile.objects.get_or_create(rawfile_id=rawfn['file_id'],
                        filetype_id=extprod.msinstrument.filetype_id, filename=fn,
                        defaults={'servershare_id': share.id, 'path': os.path.join(req['dirname'], path),
                            'md5': fakemd5, 'checked': False})
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
    # TODO return scp address to transfer file to
    # Find out something for SSH key rotation (client creates new key and uploads pubkey)
    # But how to know the client is the real client?
    # Strong secret needed, although if the client computer is used
    # By someone else we are fucked anyway
    # Rotate SSH keys to remove the danger of SSH key leaking,
    # And automate to not give the "lab laptop uploads" an actual SSH 
    # key (else theyd have to get it from admin all the time, PITA!)
    # Auto-Rotate key every sunday night or something on client (stop transferring, fix keys)
    # User file uploads get key per upload (have to wait until it is installed on the data/server
    """New files are registered in the system on this view, where producer 
    or user passes info on file (name, md5, date, etc). Auth is done 
    via a token either from web console or CLI script.
    """
    data = json.loads(request.body.decode('utf-8'))
    try:
        token = data['token']
        fn, size, md5, filedate_raw = data['fn'], data['size'], data['md5'], data['date']
    except KeyError as error:
        print('POST request to register_file with missing parameter, '
              '{}'.format(error))
        return JsonResponse({'error': 'Data passed to registration incorrect'}, status=400)
    upload = validate_token(token)
    if not upload:
        return JsonResponse({'error': 'Token invalid or expired'}, status=403)
    try:
        file_date = datetime.strftime(
            datetime.fromtimestamp(float(filedate_raw)), '%Y-%m-%d %H:%M')
    except ValueError as error:
        print('POST request to register_file with incorrect formatted '
              'date parameter {}'.format(error))
        return JsonResponse({'error': 'Date passed to registration incorrectly formatted'}, status=400)
    response = get_or_create_rawfile(md5, fn, upload.producer, size, file_date, data)
    return JsonResponse(response)


@login_required
def browser_userupload(request):
    # FIXME make sure this job is similar to transfer_file then?
    data = request.POST
    try:
        ftype = StoredFileType.objects.get(user_uploadable=True, pk=int(data['ftype_id']))
    except ValueError:
        return JsonResponse({'success': False, 'msg': 'Please select a file type '
        f'{data["ftype_id"]}'})
    except StoredFileType.DoesNotExist:
        return JsonResponse({'success': False, 'msg': 'Illegal file type to upload'})
    if not ftype.is_rawdata:
        desc = str(data.get('desc', '').strip())
        if desc == '':
            return JsonResponse({'success': False, 'msg': 'A description for this file is required'})
    elif ftype.is_folder:
        return JsonResponse({'success': False, 'msg': 'Cannot upload folder datatypes through browser'})

    try:
        archive_only = bool(int(data['archive_only']))
        is_library = bool(int(data['is_library']))
    except (ValueError, KeyError):
        return JsonResponse({'success': False, 'msg': 'Bad request, contact admin'}, status=400)
    # create userfileupload model (incl. fake token)
    producer = Producer.objects.get(shortname='admin')
    upload = create_upload_token(ftype.pk, request.user.id, producer, archive_only, is_library)
    # tmp write file 
    upfile = request.FILES['file']
    dighash = md5()
        # check if it is correct FASTA (maybe add more parsing later)
        # Flush it to disk just in case, but seek is usually enough
    with NamedTemporaryFile(mode='wb+') as fp:
        for chunk in upfile.chunks():
            fp.write(chunk)
            dighash.update(chunk)
        # stay in context until copied, else tempfile is deleted
        fp.seek(0)
        if ftype.name == 'fasta' and not any(SeqIO.parse(fp, 'fasta')):
            notfa_err_resp = {'msg': 'File is not correct FASTA', 'success': False}
            return JsonResponse(notfa_err_resp, status=403)
        dighash = dighash.hexdigest() 
        raw = get_or_create_rawfile(dighash, upfile.name, producer, upfile.size, timezone.now(), {'claimed': True})
        dst = rsjobs.create_upload_dst_web(raw['file_id'], upload.filetype.filetype)
        # Copy file to target uploadpath, after Tempfile context is gone, it is deleted
        shutil.copy(fp.name, dst)
        os.chmod(dst, 0o644)
    sfns = StoredFile.objects.filter(rawfile_id=raw['file_id'])
    if sfns.count() == 1:
        os.unlink(dst)
        return JsonResponse({'success': False, 'msg': 'This file is already in the '
            f'system: {sfns.get().filename}'}, status=403)
    elif sfns.count():
        os.unlink(dst)
        return JsonResponse({'success': False, 'msg': 'Multiple files already found, this '
            'should not happen, please inform your administrator'}, status=403)
    sfile = StoredFile.objects.create(rawfile_id=raw['file_id'],
        filename=f'{raw["file_id"]}_{upfile.name}',
        checked=True, filetype=upload.filetype,
        md5=dighash, path=settings.USERFILEDIR,
        servershare=ServerShare.objects.get(name=settings.ANALYSISSHARENAME))
    jobutil.create_job('rsync_transfer', sf_id=sfile.pk, src_path=dst)
    if not ftype.is_rawdata and upload.is_library:
        LibraryFile.objects.create(sfile=file_trf, description=libdesc)
    elif not ftype.is_rawdata:
        UserFile.objects.create(sfile=sfile, description=desc, upload=upload)
    dstfn = process_file_confirmed_ready(sfile.rawfile, sfile, upload.archive_only)
    return JsonResponse({'success': True, 'msg': 'Succesfully uploaded file to '
        f'become {dstfn} File will be accessible on storage soon.'})

    
# TODO store heartbeat of instrument, deploy config, message from backend, etc

@require_POST
def instrument_check_in(request):
    '''Returns 200 at correct token or expiring token, in which case a new token
    will be issued'''
    data = json.loads(request.body.decode('utf-8'))
    response = {'newtoken': False}
    token = data.get('token', False)
    taskid = data.get('task_id', False)
    if not data.get('client_id', False):
        return JsonResponse({'error': 'Bad request'}, status=400)
    elif not any([token, taskid]):
        return JsonResponse({'error': 'Bad request'}, status=400)
    elif taskid and not data.get('ftype', False):
        return JsonResponse({'error': 'Bad request'}, status=400)

    upload = validate_token(token) if token else False
    task = jm.Task.objects.filter(asyncid=taskid).exclude(state__in=jobutil.JOBSTATES_DONE)

    if upload and upload.producer.client_id != data['client_id']:
        # Keep the token bound to a client instrument
        return JsonResponse({'error': 'Token/client ID invalid or non-existing'},
                status=403)
    elif not upload and task.count():
        # Token for a client on a controlled system like analysis server:
        # auth by client ID and task ID knowledge
        producer = Producer.objects.get(client_id=data['client_id'])
        try:
            ftype = StoredFileType.objects.get(name=data['ftype'])
        except StoredFileType.DoesNotExist:
            return JsonResponse({'error': 'File type does not exist'}, status=403)
        print('New token issued for a valid task ID without a token')
        newtoken = create_upload_token(ftype.pk, settings.QC_USER_ID, producer)
        response.update({'newtoken': newtoken.token, 'expires': newtoken.expires})
    elif not upload:
        return JsonResponse({'error': 'Token/client ID invalid or non-existing'},
                status=403)
    elif upload.expires < timezone.now() + timedelta(settings.TOKEN_RENEWAL_WINDOW_DAYS):
        upload.expired = True
        upload.save()
        newtoken = create_upload_token(upload.filetype_id, upload.user_id, upload.producer)
        response.update({'newtoken': newtoken.token, 'expires': newtoken.expires})
    return JsonResponse(response)

 
def login_required_403_json(view_func):
    """
    Modified django's login_required to return a JsonResponse with
    403 instead of a redirect to the log-in page.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return JsonResponse({'error': 'Permission denied'}, status=403)
    return _wrapped_view


@login_required_403_json
@require_POST
def request_upload_token(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        producer = Producer.objects.get(client_id=data['producer_id'])
    except Producer.DoesNotExist:
        return JsonResponse({'error': True, 'error': 'Cannot use that file producer'}, status=403)
    except KeyError:
        producer = Producer.objects.get(shortname='admin')
    try:
        selected_ft = StoredFileType.objects.get(pk=data['ftype_id'])
    except StoredFileType.DoesNotExist:
        return JsonResponse({'error': True, 'error': 'Cannot use that file type'}, status=403)
    ufu = create_upload_token(data['ftype_id'], request.user.id, producer, data['archive_only'],
            data['is_library'] and not selected_ft.is_rawdata)
    token_info = f'{ufu.token}|{settings.KANTELEHOST}|{int(ufu.is_library)}|{int(not ufu.filetype.is_rawdata)}'
    token_ft_host_b64 = b64encode(token_info.encode('utf-8'))
    return JsonResponse({'token': ufu.token,
        'user_token': token_ft_host_b64.decode('utf-8'), 'expires': ufu.expires})


def create_upload_token(ftype_id, user_id, producer, archive_only=False, is_library=False):
    '''Generates a new UploadToken for a producer and stores it in DB'''
    token = str(uuid4())
    expi_sec = settings.MAX_TIME_PROD_TOKEN if producer.internal else settings.MAX_TIME_UPLOADTOKEN
    expiry = timezone.now() + timedelta(seconds=expi_sec)
    return UploadToken.objects.create(token=token, user_id=user_id, expired=False,
            expires=expiry, filetype_id=ftype_id, producer=producer,
            archive_only=archive_only, is_library=is_library)


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
    return {'file_id': rawfn.id, 'state': state, 'stored': stored, 
            'remote_name': rawfn.name, 'msg': msg}


def validate_token(token):
    try:
        upload = UploadToken.objects.select_related('filetype', 'producer').get(
                token=token, expired=False)
    except UploadToken.DoesNotExist as e:
        print('Token for user upload does not exist')
        return False
    else:
        if upload.expires < timezone.now():
            print('Token expired')
            upload.expired = True
            upload.save()
            return False
        elif upload.expired:
            print('Token expired')
            return False
        return upload


# /files/transferstate
@require_POST
def get_files_transferstate(request):
    data =  json.loads(request.body.decode('utf-8'))
    try:
        token, fnid = data['token'], data['fnid']
    except KeyError as error:
        print(f'Request to get transferstate with missing parameter, {error}')
        return JsonResponse({'error': 'Bad request'}, status=400)

    upload = validate_token(token)
    if not upload:
        return JsonResponse({'error': 'Token invalid or expired'}, status=403)
    # Also do registration here? if MD5? prob not.
    rfn = RawFile.objects.filter(pk=fnid)
    if not rfn.count():
        return JsonResponse({'error': f'File with ID {fnid} cannot be found in system'}, status=404)
    rfn = rfn.get()
    if rfn.producer != upload.producer:
        # In case the file has been moved to another instrument or the instrument API key
        # is wrong here (unlikely right?)
        return JsonResponse({'error': f'File with ID {rfn.id} is not from producer  {upload.producer.name}'}, status=403)
    # FIXME if somehow really bad timing, there will be multiple sfns?
    sfns = rfn.storedfile_set.filter(filetype=upload.filetype, mzmlfile__isnull=True)
    if not sfns.count():
        # has not been reported as transferred,
        tstate = 'transfer'
    elif sfns.count() > 1:
        # Now behaviour specifies there can only be one copy of a raw file
        # What happens if there is a copy e.g. on a different server?
        errmsg = 'Problem, there are multiple stored files with that raw file ID'
        print(errmsg)
        return JsonResponse({'error': errmsg}, status=409)
    else:
        # File in system, should be transferred and being rsynced/unzipped, or
        # errored, or done.
        sfn = sfns.select_related('filetype', 'userfile', 'libraryfile').get()
        up_dst = rsjobs.create_upload_dst_web(rfn.pk, sfn.filetype.filetype)
        rsync_jobs = jm.Job.objects.filter(funcname='rsync_transfer',
                kwargs__sf_id=sfn.pk, kwargs__src_path=up_dst).order_by('-timestamp')
        # fetching from DB here to avoid race condition in if/else block
        try:
            last_rsjob = rsync_jobs.last()
        except jm.Job.DoesNotExist:
            last_rsjob = False
        # Refresh to make sure we dont get race condition where it is checked
        # while we fetching jobs above and the non-checked/done job will result
        # in a retransfer
        sfn.refresh_from_db()

        if sfn.checked:
            # File transfer and check finished
            tstate = 'done'
            if (not AnalysisResultFile.objects.filter(sfile_id=sfn) and not
                    PDCBackedupFile.objects.filter(storedfile_id=sfn.id)):
                # No analysis result or PDC file, then do some processing work
                process_file_confirmed_ready(rfn, sfn, upload.archive_only)
        # FIXME this is too hardcoded data model which will be changed one day,
        # needs to be in Job class abstraction!

        elif not last_rsjob:
            # There is no rsync job for this file, means it's old or somehow
            # errored # TODO how to report to user? File is also not OK checked
            tstate = 'wait'
        elif last_rsjob.state not in jobutil.JOBSTATES_DONE:
            # File being rsynced and optionally md5checked (or it crashed, job
            # errored, revoked, wait for system or admin to catch job)
            # WARNING: this did not work when doing sfn.filejob_set.filter ?
            # A second call to this route would fire the rsync/md5 job again,
            # until the file was checked. But in theory it'd work, and by hand too.
            # Maybe a DB or cache thing, however 3seconds between calls should be enough?
            # Maybe NGINX caches stuff, add some sort of no-cache into the header of request in client producer.py
            tstate = 'wait'

        elif last_rsjob.state == jobutil.Jobstates.DONE:
            # MD5 on disk is not same as registered MD5, corrupted transfer
            # reset MD5 on stored file to make sure no NEW stored files are created
            # basically setting its state to pre-transfer state
            sfn.md5 = rfn.source_md5
            sfn.save()
            tstate = 'transfer'

        else:
            # There is an unlikely rsync job which is canceled, requeue it
            jobutil.create_job('rsync_transfer', sf_id=sfn.pk, src_path=up_dst)
            tstate = 'wait'
    response = {'transferstate': tstate}
    return JsonResponse(response)


def process_file_confirmed_ready(rfn, sfn, archive_only):
    """Processing of backup, QC, library/userfile after transfer has succeeded
    (MD5 checked) for newly arrived MS other raw data files (not for analysis etc)
    Files that are for archiving only are also deleted from the archive share after
    backing up.
    """
    is_ms = hasattr(rfn.producer, 'msinstrument')
    is_active_ms = is_ms and rfn.producer.internal and rfn.producer.msinstrument.active
    jobutil.create_job('create_pdc_archive', sf_id=sfn.id, isdir=sfn.filetype.is_folder)
    if archive_only:
        jobutil.create_job('purge_files', sf_ids=[sfn.pk])
    fn = sfn.filename
    if 'QC' in fn and 'hela' in fn.lower() and not 'DIA' in fn and is_active_ms:
        singlefile_qc(sfn.rawfile, sfn)
        newname = fn
    elif hasattr(sfn, 'libraryfile'):
        newname = f'libfile_{sfn.libraryfile.id}_{rfn.name}'
        jobutil.create_job('move_single_file', sf_id=sfn.id, dst_path=settings.LIBRARY_FILE_PATH,
                newname=newname)
    elif hasattr(sfn, 'userfile'):
        newname = f'userfile_{rfn.id}_{rfn.name}'
        # FIXME can we move a folder!?
        jobutil.create_job('move_single_file', sf_id=sfn.id, dst_path=settings.USERFILEDIR,
                newname=newname)
    else:
        newname = sfn.filename
    return newname


@require_POST
def transfer_file(request):
    # FIXME HTTP need long view time 
    # 
    # FIXME add share name to upload to and path
    '''HTTP based file upload'''
    data = request.POST
    try:
        token = data['token']
        fn_id = int(data['fn_id'])
        fname = data['filename']
    except KeyError as error:
        print('POST request to transfer_file with missing parameter, '
              '{}'.format(error))
        return JsonResponse({'error': 'Bad request'}, status=400)
    except ValueError:
        print('POST request to transfer_file with incorrect fn_id, '
              '{}'.format(error))
        return JsonResponse({'error': 'Bad request'}, status=400)
    libdesc = data.get('libdesc', False)
    userdesc = data.get('userdesc', False)
    upload = validate_token(token)
    if not upload:
        return JsonResponse({'error': 'Token invalid or expired'}, status=403)
    elif upload.is_library and not libdesc:
        return JsonResponse({'error': 'Library file needs a description'}, status=403)
    elif not upload.is_library and not upload.filetype.is_rawdata and not userdesc:
        return JsonResponse({'error': 'User file needs a description'}, status=403)
    # First check if everything is OK wrt rawfile/storedfiles
    try:
        rawfn = RawFile.objects.get(pk=fn_id)
    except RawFile.DoesNotExist:
        errmsg = 'File with ID {} has not been registered yet, cannot transfer'.format(fn_id)
        print(errmsg)
        return JsonResponse({'state': 'error', 'problem': 'NOT_REGISTERED', 'error': errmsg}, status=403)
    sfns = StoredFile.objects.filter(rawfile_id=fn_id)
    if sfns.count():
        # By default do not overwrite, although deleted files could trigger this
        # as well. In that case, have admin remove the files from DB.
        # TODO create exception for that if ever needed? data['overwrite'] = True?
        # Also look at below get_or_create call and checking created
        return JsonResponse({'error': 'This file is already in the '
            f'system: {sfns.get().filename}, if you are re-uploading a previously '
            'deleted file, consider reactivating from backup, or contact admin'}, status=403)
    upfile = request.FILES['file']
    dighash = md5()
    upload_dst = rsjobs.create_upload_dst_web(rawfn.pk, upload.filetype.filetype)
    # Write file from /tmp (or in memory if small) to its destination in upload folder
    # We could do shutil.move() if /tmp file, for faster performance, but on docker
    # with bound host folders this is a read/write operation and not a simple atomic mv
    # That means we can do MD5 check at hardly an extra cost, it is hardly slower than
    # not doing it if we're r/w anyway. Thus we can skip using an extra bg job
    if upload.filetype.is_folder and len(upload.filetype.stablefiles) > 0:
        # folder data is uploaded zipped and will be unzipped after rsync
        # contains a stablefile to MD5 check on, post-unzip
        with open(upload_dst, 'wb+') as fp:
            for chunk in upfile.chunks():
                fp.write(chunk)
    else:
        # No predictable file inside zipped folder if any, so we instead do MD5 on
        # entire zipped folder or raw file which is uploaded.
        with open(upload_dst, 'wb+') as fp:
            for chunk in upfile.chunks():
                fp.write(chunk)
                dighash.update(chunk)
        dighash = dighash.hexdigest() 
        if dighash != rawfn.source_md5:
            os.unlink(upload_dst)
            return JsonResponse({'error': 'Failed to upload file, checksum differs from reported MD5, possibly corrupted in transfer or changed on local disk', 'state': 'error'})
    os.chmod(upload_dst, 0o644)
    # Now prepare for move to proper destination
    if upload.archive_only:
        dstshare = ServerShare.objects.get(name=settings.ARCHIVESHARENAME)
    else:
        dstshare = ServerShare.objects.get(name=settings.TMPSHARENAME)
    fname = fname if rawfn.producer.internal else f'{rawfn.pk}_{fname}'
    file_trf, created = StoredFile.objects.get_or_create(
            rawfile=rawfn, filetype=upload.filetype, md5=rawfn.source_md5,
            defaults={'servershare': dstshare, 'path': settings.TMPPATH,
                'filename': fname, 'checked': False})
    if not created:
        # This could happen in the future when there is some kind of bypass of the above
        # check sfns.count(). 
        print('File already registered as transferred')
    elif upload.is_library:
        LibraryFile.objects.create(sfile=file_trf, description=libdesc)
    elif not upload.filetype.is_rawdata:
        UserFile.objects.create(sfile=file_trf, description=userdesc, upload=upload)
    jobutil.create_job('rsync_transfer', sf_id=file_trf.pk, src_path=upload_dst)
    return JsonResponse({'fn_id': fn_id, 'state': 'ok'})


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
    analysis = Analysis.objects.create(user_id=settings.QC_USER_ID,
                        name='{}_{}_{}'.format(rawfile.producer.name, rawfile.name, rawfile.date))
    jobutil.create_job('run_longit_qc_workflow', sf_id=storedfile.id, analysis_id=analysis.id,
            wfv_id=wf_id, dbfn_id=settings.LONGQC_FADB_ID, params=params)


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


def zip_instrument_upload_pkg(prod, datadisk, runtransferfile):
    tmpfp, zipfilename = mkstemp()
    shutil.copy('/assets/producer.zip', zipfilename)
    with zipfile.ZipFile(zipfilename, 'a') as zipfp:
        zipfp.write('rawstatus/file_inputs/upload.py', 'upload.py')
        zipfp.write('rawstatus/file_inputs/producer.bat', 'transfer.bat')
        zipfp.writestr('transfer_config.json', runtransferfile)
    return zipfilename


def zip_user_upload_pkg():
    tmpfp, zipfilename = mkstemp()
    with zipfile.ZipFile(zipfilename, 'w') as zipfp:
        zipfp.write('rawstatus/file_inputs/upload.py', 'upload.py')
        zipfp.write('rawstatus/file_inputs/kantele_upload.sh', 'kantele_upload.sh')
    return zipfilename


@login_required
@require_GET
def download_instrument_package(request):
    # TODO instrument page with all instruments, which can have configs to be saved
    # make new app for this in django
    # configs will then be auto-downloaded when changing datadisk, outbox name,
    # instrument name, etc
    # and staff can create new instruments when they like
    try:
        client = request.GET['client']
    except KeyError:
        return HttpResponseForbidden()
    if client == 'instrument':
        try:
            prod = Producer.objects.select_related('msinstrument').get(pk=request.GET['prod_id'])
        except Producer.DoesNotExist:
            return HttpResponseForbidden()
        fname_prefix = prod.name
        datadisk = f'{request.GET["datadisk"][0]}'
        runtransferfile = json.dumps({
            'outbox': f'{datadisk}\outbox',
            'zipbox': f'{datadisk}\zipbox',
            'donebox': f'{datadisk}\donebox',
            'producerhostname': prod.name,
            'client_id': prod.client_id,
            'filetype_id': prod.msinstrument.filetype_id,
            'is_folder': 1 if prod.msinstrument.filetype.is_folder else 0,
            'host': settings.KANTELEHOST,
            'md5_stable_fns': prod.msinstrument.filetype.stablefiles,
            })
        if 'configonly' in request.GET and request.GET['configonly'] == 'true':
            resp = HttpResponse(runtransferfile, content_type='application/json')
            resp['Content-Disposition'] = 'attachment; filename="transfer_config.json"'
            return resp
        # strip datadisk so only get first letter
        zipfn = zip_instrument_upload_pkg(prod, datadisk, runtransferfile)
    elif client == 'user':
        fname_prefix = 'kantele'
        zipfn = zip_user_upload_pkg()
    else:
        return HttpResponseForbidden()
    resp = FileResponse(open(zipfn, 'rb'))
    resp['Content-Disposition'] = f'attachment; filename="{fname_prefix}_filetransfer.zip"'
    return resp


def show_old_new_projects(request):
    maxtime_nonint = timezone.now() - timedelta(settings.MAX_MZML_STORAGE_TIME_POST_ANALYSIS)
    allp = Project.objects.filter(active=True)
    # make an aggregate for gt / lt  maxtime, or just filter stuff?
    pass


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
    all_old_mzmls = old_searched_mzmls.union(lcmzmls, old_nonsearched_mzml)
    # TODO auto remove QC raw files of certain age? make sure you can get them back when needed though.

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
            StoredFile.objects.get_or_create(rawfile_id=rawfn['file_id'], filetype_id=ftid,
                    filename=fn, defaults={'servershare_id': tmpshare, 'path': '',
                        'md5': fakemd5, 'checked': False})
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
