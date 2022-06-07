import json
import requests
from datetime import datetime 

from celery import states
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import F

from jobs import models
from jobs.jobs import Jobstates, create_job, send_slack_message
from rawstatus.models import (RawFile, StoredFile, ServerShare, StoredFileType,
                              SwestoreBackedupFile, PDCBackedupFile, Producer)
from analysis.models import AnalysisResultFile, NextflowSearch
from analysis.views import write_analysis_log
from dashboard import views as dashviews
from datasets import views as dsviews
from datasets.models import DatasetRawFile, Dataset
from kantele import settings

from datasets import jobs as dsjobs
from rawstatus import jobs as rsjobs
from analysis import jobs as anjobs

alljobs = [
        dsjobs.RenameDatasetStorageLoc,
        dsjobs.MoveFilesToStorage,
        dsjobs.MoveFilesStorageTmp,
        dsjobs.ConvertDatasetMzml,
        dsjobs.ConvertFileMzml,
        dsjobs.DeleteActiveDataset,
        dsjobs.DeleteDatasetMzml,
        dsjobs.BackupPDCDataset,
        dsjobs.ReactivateDeletedDataset,
        dsjobs.DeleteDatasetPDCBackup,
        dsjobs.RenameProject,
        rsjobs.GetMD5,
        rsjobs.CreatePDCArchive,
        rsjobs.RestoreFromPDC,
        rsjobs.UnzipRawFolder,
        rsjobs.RenameFile,
        rsjobs.MoveSingleFile,
        rsjobs.DeleteEmptyDirectory,
        rsjobs.PurgeFiles,
        rsjobs.DownloadPXProject,
        rsjobs.RegisterExternalFile,
        anjobs.RunLongitudinalQCWorkflow,
        anjobs.RunNextflowWorkflow,
        anjobs.RunLabelCheckNF,
        anjobs.RefineMzmls,
        anjobs.PurgeAnalysis,
        ]
jobmap = {job.refname: job for job in alljobs}


def set_task_done(task_id):
    task = models.Task.objects.get(asyncid=task_id)
    task.state = states.SUCCESS
    task.save()


def taskclient_authorized(client_id, possible_ids):
    """Possibly use DB in future"""
    return client_id in possible_ids


@require_POST
def task_failed(request):
    data = json.loads(request.body.decode('utf-8'))
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], settings.CLIENT_APIKEYS):
        return HttpResponseForbidden()
    print('Failed task registered task id {}'.format(data['task']))
    task = models.Task.objects.get(asyncid=data['task'])
    task.state = states.FAILURE
    task.save()
    if data['msg']:
        models.TaskError.objects.create(task_id=task.id, message=data['msg'])
    return HttpResponse()


@require_POST
def update_storage_loc_dset(request):
    """Updates storage_loc on dset after a dset update storage job"""
    data = json.loads(request.body.decode('utf-8'))
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    Dataset.objects.filter(pk=data['dset_id']).update(storage_loc=data['storage_loc'])
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def update_storagepath_file(request):
    # FIXME tests!
    data = json.loads(request.body.decode('utf-8'))
    print('Updating storage task finished')
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY, settings.ANALYSISCLIENT_APIKEY]):
        return HttpResponseForbidden()
    if 'fn_id' in data:
        sfile = StoredFile.objects.get(pk=data['fn_id'])
        sfile.servershare = ServerShare.objects.get(name=data['servershare'])
        sfile.path = data['dst_path']
        if 'newname' in data:
            sfile.filename = data['newname']
        sfile.save()
    elif 'fn_ids' in data:
        sfns = StoredFile.objects.filter(pk__in=[int(x) for x in data['fn_ids']])
        sfns.update(path=data['dst_path'])
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def renamed_project(request):
    """
    After project renaming on disk, we need to set all paths of the storedfile objects
    to the new path name, and rename the project in the DB as well.
    """
    data = json.loads(request.body.decode('utf-8'))
    print('Updating storage task finished')
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY, settings.ANALYSISCLIENT_APIKEY]):
        return HttpResponseForbidden()
    # TODO this updates also deleted files? Good maybe in case restoring backup?
    for dset in Dataset.objects.filter(runname__experiment__project_id=data['proj_id']):
        newstorloc = dsviews.rename_storage_loc_toplvl(data['newname'], dset.storage_loc)
        dset.storage_loc = newstorloc
        dset.save()
        StoredFile.objects.filter(rawfile__datasetrawfile__dataset=dset).update(path=newstorloc)
    set_task_done(data['task'])
    return HttpResponse()


@require_POST
def set_md5(request):
    if 'client_id' not in request.POST or not taskclient_authorized(
            request.POST['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    StoredFile.objects.filter(pk=request.POST['sfid']).update(md5=request.POST['md5'],
            checked=request.POST['source_md5'] == request.POST['md5'])
    print('Stored file MD5 checked and saved')
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


@login_required
@require_POST
def pause_job(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        job = models.Job.objects.get(pk=req['item_id'])
    except models.Job.DoesNotExist:
        return JsonResponse({'error': 'This job does not exist (anymore), it may have been deleted'}, status=403)
    ownership = get_job_ownership(job, request)
    if not ownership['owner_loggedin'] and not ownership['is_staff']:
        return JsonResponse({'error': 'Only job owners and admin can pause this job'}, status=403)
    elif not is_job_retryable(job):
        return JsonResponse({'error': 'Job type {} cannot be paused/resumed'.format(job.funcname)}, status=403)
    elif job.state not in [Jobstates.PENDING, Jobstates.ERROR]:
        return JsonResponse({'error': 'Only jobs that are pending for queueing or errored can be paused'}, status=403)
    if job.state == Jobstates.ERROR:
        job.task_set.exclude(state=states.SUCCESS).delete()
        if hasattr(job, 'joberror'):
            job.joberror.delete()
    job.state = Jobstates.WAITING
    job.save()
    return JsonResponse({}) 
    

@login_required
@require_POST
def resume_job(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        job = models.Job.objects.get(pk=req['item_id'])
    except models.Job.DoesNotExist:
        return JsonResponse({'error': 'This job does not exist (anymore), it may have been deleted'}, status=403)
    ownership = get_job_ownership(job, request)
    if not ownership['owner_loggedin'] and not ownership['is_staff']:
        return JsonResponse({'error': 'Only job owners and admin can resume this job'}, status=403)
    elif job.state not in Jobstates.WAITING:
        return JsonResponse({'error': 'Only jobs that are paused can be resumed, this job is in state '
        '{}'.format(job.state)}, status=403)
    job.state = Jobstates.PENDING
    job.save()
    return JsonResponse({}) 
    

def revoke_job(jobid, request):
    try:
        job = models.Job.objects.get(pk=jobid)
    except models.Job.DoesNotExist:
        return JsonResponse({'error': 'This job does not exist (anymore), it may have been deleted'}, status=403)
    ownership = get_job_ownership(job, request)
    if not ownership['owner_loggedin'] and not ownership['is_staff']:
        return JsonResponse({'error': 'Only job owners and admin can delete this job'}, status=403)
    job.state = Jobstates.REVOKING
    job.save()
    return JsonResponse({}) 


@login_required
@require_POST
def delete_job(request):
    req = json.loads(request.body.decode('utf-8'))
    return revoke_job(req['item_id'], request)


@require_POST
def purge_storedfile(request):
    """Ran after a job has deleted a file from the filesystem, sets
    file DB entry to purged"""
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY,
                                settings.SWESTORECLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.filter(pk=data['sfid']).select_related('filetype').get()
    sfile.purged, sfile.deleted = True, True
    sfile.save()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def removed_emptydir(request):
    """Ran after a job has deleted an empty dir from the filesystem"""
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY,
                                settings.SWESTORECLIENT_APIKEY]):
        return HttpResponseForbidden()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def register_external_file(request):
    """Storedfile and rawfn update proper md5 and set checked
    Creates job to add file to dset to move file to storage.
    This is for when you download files from some repository and you 
    thus do not know MD5 in advance, it is set on receival.
    """
    data = json.loads(request.body.decode('utf-8'))
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    dataset = {'dataset_id': data['dset_id'], 'removed_files': {},
               'added_files': {1: {'id': data['raw_id']}}}
    StoredFile.objects.filter(pk=data['sf_id']).update(md5=data['md5'], checked=True)
    RawFile.objects.filter(pk=data['raw_id']).update(source_md5=data['md5'])
    dsviews.save_or_update_files(dataset)
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def unzipped_folder(request):
    """Changes file name in DB after having completed unzip (remove .zip)"""
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.get(pk=request.POST['sfid'])
    sfile.md5 = request.POST['md5']
    sfile.checked = request.POST['source_md5'] == request.POST['md5']
    sfile.filename = sfile.filename.rstrip('.zip')
    sfile.save()
    print('Stored file MD5 checked and saved')
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


@require_POST
def created_pdc_archive(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    backup = PDCBackedupFile.objects.filter(storedfile_id=data['sfid'])
    backup.update(pdcpath=data['pdcpath'], deleted=False, success=True)
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


@require_POST
def restored_archive_file(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.STORAGECLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.filter(pk=data['sfid'])
    sfile.update(deleted=False, purged=False)
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


@require_POST
def created_swestore_backup(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.SWESTORECLIENT_APIKEY]):
        return HttpResponseForbidden()
    backup = SwestoreBackedupFile.objects.filter(storedfile_id=data['sfid'])
    backup.update(swestore_path=data['swestore_path'], success=True)
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()


@require_POST
def created_mzml(request):
    """For the three step windows convert tasks"""
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    storedfile = StoredFile.objects.get(pk=request.POST['sfid'])
    storedfile.filename = request.POST['filename']
    storedfile.deleted = False
    storedfile.save()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def scp_mzml(request):
    """For the three step windows convert tasks, next step is MD5"""
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def analysis_run_done(request):
    data = json.loads(request.body.decode('utf-8'))
    if ('client_id' not in data or
            data['client_id'] not in settings.CLIENT_APIKEYS):
        return HttpResponseForbidden()
    if 'log' in data:
        write_analysis_log(data['log'], data['analysis_id'])
    if 'task' in data:
        set_task_done(data['task'])
    send_slack_message('{}: Analysis of {} is now finished'.format(data['user'], data['name']), 'general')
    return HttpResponse()


@require_POST
def mzml_convert_or_refine_file_done(request):
    """Converted/Refined mzML file already copied to analysis result storage 
    server with MD5, fn, path. This function then queues a job to move it to 
    dataset directory from the analysis dir"""
    # FIXME need to remove the empty dir after moving all the files, how?
    # create cleaning task queue on ana server
    data = request.POST
    if ('client_id' not in data or
            data['client_id'] != settings.ANALYSISCLIENT_APIKEY):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.select_related('rawfile__datasetrawfile__dataset').get(pk=data['fn_id'])
    sfile.path = data['outdir']
    sfile.filename = data['filename']
    sfile.md5 = data['md5']
    sfile.checked = True
    sfile.deleted = False
    sfile.save()
    create_job('move_single_file', sf_id=sfile.id, dst_path=sfile.rawfile.datasetrawfile.dataset.storage_loc)
    return HttpResponse()


@require_POST
def store_longitudinal_qc(request):
    data = json.loads(request.body.decode('utf-8'))
    if ('client_id' not in data or
            data['client_id'] not in settings.CLIENT_APIKEYS):
        return HttpResponseForbidden()
    elif data['state'] == 'error':
        dashviews.fail_longitudinal_qc(data)
    else:
        dashviews.store_longitudinal_qc(data)
        send_slack_message('QC run for {} is now finished: {}'.format(data['instrument'], data['filename']), 'lab')
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@require_POST
def store_analysis_result(request):
    """Stores the reporting of a transferred analysis result file,
    checks its md5"""
    data = request.POST
    # create analysis file
    if ('client_id' not in data or
            data['client_id'] != settings.ANALYSISCLIENT_APIKEY):
        return HttpResponseForbidden()
    anashare = ServerShare.objects.get(name=settings.ANALYSISSHARENAME)
    try:
        ftypeid = {x.name: x.id for x in StoredFileType.objects.all()}[data['ftype']]
    except KeyError:
        return HttpResponseForbidden('File type does not exist')

    # Reruns lead to trying to store files multiple times, avoid that here:
    sfile, created  = StoredFile.objects.get_or_create(rawfile_id=data['fn_id'], 
            md5=data['md5'],
            defaults={'filetype_id': ftypeid, 'servershare': anashare, 
                'path': data['outdir'], 'checked': True, 'filename': data['filename']})
    if created:
        AnalysisResultFile.objects.create(analysis_id=data['analysis_id'], sfile=sfile)
    else:
        # FIXME if file already stored, what happens? message?
        pass
    return HttpResponse()


def get_job_analysis(job):
    try:
        analysis = job.nextflowsearch.analysis
    except NextflowSearch.DoesNotExist:
        analysis = False 
    return analysis


def get_job_ownership(job, request):
    """returns {'ownertype': user/admin, 'usernames': [], 'owner_loggedin': T/F}
    """
    owner_loggedin = False
    ownertype = 'user'
    ana = get_job_analysis(job)
    if ana:
        usernames = [ana.user.username]
        owner_loggedin = request.user.id == ana.user.id
    else:
        fjs = job.filejob_set.select_related('storedfile__rawfile__datasetrawfile__dataset')
        try:
            users = list({y.user for x in fjs for y in x.storedfile.rawfile.datasetrawfile.dataset.datasetowner_set.all()})
        except DatasetRawFile.DoesNotExist:
            usernames = list({x.storedfile.rawfile.producer.name for x in fjs})
            ownertype = 'admin'
        else:
            usernames = [x.username for x in users]
            owner_loggedin = request.user.id in [x.id for x in users]
    return {'usernames': usernames, 'owner_loggedin': owner_loggedin, 'type': ownertype,
             'is_staff': request.user.is_staff}
    

def is_job_retryable_ready(job, tasks=False):
    return is_job_retryable(job) and is_job_ready(job)


def is_job_retryable(job, tasks=False):
    return job.funcname in jobmap and jobmap[job.funcname].retryable


def is_job_ready(job=False, tasks=False):
    if tasks is False:
        tasks = models.Task.objects.filter(job_id=job.id)
    if {t.state for t in tasks}.difference(states.READY_STATES):
        return False
    return True


@login_required
def retry_job(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    try:
        job = models.Job.objects.get(pk=req['item_id'])
    except models.Job.DoesNotExist:
        return JsonResponse({'error': 'This job does not exist (anymore), it may have been deleted'}, status=403)
    ownership = get_job_ownership(job, request)
    if ownership['is_staff'] and is_job_retryable(job):
        do_retry_job(job, force=True)
    elif ownership['owner_loggedin'] and is_job_retryable_ready(job):
        do_retry_job(job)
    else:
        return JsonResponse({'error': 'You are not allowed to retry this job'}, status=403)
    return JsonResponse({})


def do_retry_job(job, force=False):
    tasks = models.Task.objects.filter(job=job)
    if not is_job_retryable(job) and not force:
        print('Cannot retry job which is not idempotent')
        return
    if not is_job_ready(job=job, tasks=tasks) and not force:
        print('Tasks not all ready yet, will not retry, try again later')
        return
    tasks.exclude(state=states.SUCCESS).delete()
    try:
        job.joberror.delete()
    except models.JobError.DoesNotExist:
        pass
    job.state = Jobstates.PENDING
    job.save()
