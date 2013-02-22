from django.shortcuts import redirect, render
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from metadata.models import Dataset
from news.models import Entry
import json, os
import consts

def home(request, message=None):
    # This should be via a class interface to Vainamoinen if specified
    try:
        with open(os.path.join('/mnt','kalevalatmp', 'infofile_status.json')) as fp:
            status = json.load(fp)
    except:
        pass # FIXME logging

    news = Entry.objects.all().order_by('-date')[:5]
    
    if request.user.is_authenticated():
        datasets = Dataset.objects.filter(datasetowner__owner=request.user).order_by('-date')[:5]
    else:
        datasets = None
    return render(request, 'kantele/index.html', {'news': news, 'status': status, 
        'datasets': datasets} )

@login_required
def all_user_datasets(request):
    datasets = Dataset.objects.filter(datasetowner__owner=request.user).order_by('-date')
    return render(request, 'kantele/mydatasets.html', {'datasets': datasets})


def logout_page(request):
    logout(request)
    return redirect('/kantele')
