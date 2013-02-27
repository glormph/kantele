import json
from django.http import HttpResponse
from rawstatus import rawstatus_querier
# Create your views here.


def raw_file_processed(request):
    fns = request.GET.getlist('fn')
    report = rawstatus_querier.get_statuses(fns)
    return HttpResponse(json.dumps(report))

