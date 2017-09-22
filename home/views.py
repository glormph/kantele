from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from datasets import models as dsmodels

@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {}
    return render(request, 'home/home.html', context)


@login_required
def show_datasets(request):
    dsmodels.DatasetComponentState

