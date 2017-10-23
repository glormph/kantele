from django.http import (HttpResponseForbidden, HttpResponse)

from kantele import settings
from rawstatus.models import StoredFile
from jobs.views import set_task_done, taskclient_authorized


def create_mzml(request):
    data = request.POST
    if 'client_id' not in data or not taskclient_authorized(
            data['client_id'], [settings.MZMLCLIENT_APIKEY]):
        return HttpResponseForbidden()
    sfile = StoredFile(rawfile_id=data['rawfile_id'], filetype='mzml',
                       servershare=data['servershare'], path=data['path'],
                       filename=fname, md5=data['md5'])
    sfile.save()
    if 'task' in request.POST:
        set_task_done(request.POST['task'])
    return HttpResponse()
