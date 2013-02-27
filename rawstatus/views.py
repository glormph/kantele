from django.http import HttpResponse
from db import dbaccess
# Create your views here.

db = dbaccess.DatabaseAccess()

def raw_file_processed(request, fn):
    status = db.get_rawfile_processed_status(fn)
    if status:
        return HttpResponse('done')
    else:
        return HttpResponse('not found')

