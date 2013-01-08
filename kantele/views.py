from django.shortcuts import render, HttpResponse
import json

def home(request):
    try:
        with open('infofile_status.json') as fp:
            status = json.load(fp)
    except:
        pass # FIXME logging

    return render(request, 'kantele/index.html', {'status': status} )
