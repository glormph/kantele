from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from collections import OrderedDict

from datasets import models as dsmodels


@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {'username': request.user.username}
    return render(request, 'home/home.html', context)


@login_required
def show_datasets(request):
    response = {
        'components': [x.name for x in dsmodels.DatasetComponent.objects.all()]
    }
    dsets = OrderedDict()
    for dcst in dsmodels.DatasetComponentState.objects.select_related(
            'dataset__runname__experiment__project', 'dtcomp__component',
            'dataset__hiriefdataset__hirief'):
        try:
            dsets[dcst.dataset.id][dcst.dtcomp.component.name] = dcst.state
        except KeyError:
            dsets[dcst.dataset.id] = {
                'id': dcst.dataset.id,
                'own': dcst.dataset.user_id == request.user.id,
                'usr': dcst.dataset.user.username,
                'proj': dcst.dataset.runname.experiment.project.name,
                'exp': dcst.dataset.runname.experiment.name,
                'run': dcst.dataset.runname.name,
                'dtype': dcst.dataset.datatype.name,
                'selected': False,
                dcst.dtcomp.component.name: dcst.state,
            }
            if hasattr(dcst.dataset, 'hiriefdataset'):
                dsets[dcst.dataset.id]['hr'] = str(dcst.dataset.hiriefdataset.hirief)
    response['dsets'] = dsets
    return JsonResponse(response)


