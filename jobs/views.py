from celery import states
from django.http import (HttpResponseForbidden, HttpResponse,
                         HttpResponseNotAllowed)
from django.contrib.auth.decorators import login_required
from jobs import models
from jobs.jobs import Jobstates, is_job_ready
from rawstatus.models import (RawFile, StoredFile, ServerShare,
                              SwestoreBackedupFile)
from kantele import settings as config


def set_task_done(task_id):
    task = models.Task.objects.get(asyncid=task_id)
    task.state = states.SUCCESS
    task.save()


def taskclient_authorized(client_id, possible_ids):
    """Possibly use DB in future"""
    return client_id in possible_ids


def task_failed(request):
    if not request.method == 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    if 'client_id' not in request.POST or not taskclient_authorized(
            request.POST['client_id'], config.CLIENT_APIKEYS):
        return HttpResponseForbidden()
    print('Failed task registered task id {}'.format(request.POST['task']))
    task = models.Task.objects.get(asyncid=request.POST['task'])
    task.state = states.FAILURE
    task.save()
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


def created_mzml(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


def scp_mzml(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [config.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile.objects.get(pk=data['sfid'])
    sfile.md5 = data['md5']
    sfile.save()
    if 'task' in data:
        set_task_done(data['task'])
    return HttpResponse()


@login_required
def retry_job(request, job_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    job = models.Job.objects.get(pk=job_id)
    tasks = models.Task.objects.filter(job_id=job_id)
    if not is_job_ready(job=job, tasks=tasks):
        print('Tasks not all ready yet, will not retry, try again later')
        return HttpResponse()
    tasks.exclude(state=states.SUCCESS).delete()
    try:
        job.joberror.delete()
    except models.JobError.DoesNotExist:
        pass
    job.state = Jobstates.PENDING
    job.save()
    return HttpResponse()
