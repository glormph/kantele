from django.shortcuts import redirect, render
from django.contrib.auth import logout
from metadata.models import Dataset
import json

def home(request):
    try:
        with open('infofile_status.json') as fp:
            status = json.load(fp)
    except:
        pass # FIXME logging

    if request.user.is_authenticated():
        datasets =  Dataset.objects.filter(user=request.user)
        templates = 1
    else:
        datasets = None
        templates = None
    return render(request, 'kantele/index.html', {'status': status, 
        'datasets': datasets, 'templates': templates} )


def logout_page(request):
    logout(request)
    return redirect('/kantele')
