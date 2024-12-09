from collections import defaultdict
import json

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
from django.shortcuts import render

from corefac import models as cm
from datasets import models as dm


@staff_member_required
@login_required
@require_GET
def corefac_home(request):
    protos = {}
    all_doi = defaultdict(list)
    for pop in cm.PrepOptionProtocol.objects.all():
        all_doi[pop.paramopt_id].append({'version': pop.version, 'doi': pop.doi})
        
    # create following JSON:
    # {1: { id: 1, title: Cleanup, methods: [{name: SP3, versions: [(v1, doi123), ]}]}
    for spo in dm.SampleprepParameterOption.objects.all().values('param__title', 'param__pk',
            'value', 'pk', 'param__active', 'active'):
        versions = all_doi[spo['pk']] if spo['pk'] in all_doi else []
        if spo['param__pk'] not in protos:
            protos[spo['param__pk']] = {'id': spo['param__pk'], 'title': spo['param__title'],
                    'active': spo['param__active'], 'methods': []}
        protos[spo['param__pk']]['methods'].append({'name': spo['value'], 'id': spo['pk'],
            'versions': versions, 'active': spo['active']})
    context = {'ctx': {'protocols': protos}}
    return render(request, 'corefac/corefac.html', context)


@staff_member_required
@login_required
@require_POST
def add_sampleprep_method(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        param_id, name = req['param_id'], req['newname']
    except KeyError:
        return JsonResponse({'error': 'Bad request to add sampleprep method, contact admin'},
                status=400)
    spo, cr = dm.SampleprepParameterOption.objects.get_or_create(param_id=param_id, value=name)
    if not cr:
        return JsonResponse({'error': 'A parameter with this name already exists'}, status=400)
    return JsonResponse({'id': spo.pk})


@staff_member_required
@login_required
def add_sampleprep_method_version(request):
    pass


@staff_member_required
@login_required
@require_POST
def edit_sampleprep_method(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        paramopt_id, name = req['paramopt_id'], req['newname']
    except KeyError:
        return JsonResponse({'error': 'Bad request to edit sampleprep method, contact admin'},
                status=400)
    spo = dm.SampleprepParameterOption.objects.filter(pk=paramopt_id)
    if not spo.count():
        return JsonResponse({'error': 'Could not find method, contact admin'}, status=400)
    spo.update(value=name)
    return JsonResponse({})


@staff_member_required
@login_required
@require_POST
def edit_sampleprep_method_version(request):
    req = json.loads(request.body.decode('utf-8'))
    pass
    return JsonResponse({})


@staff_member_required
@login_required
def disable_sampleprep_method(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        paramopt_id = req['paramopt_id']
    except KeyError:
        return JsonResponse({'error': 'Bad request to disable sampleprep method, contact admin'},
                status=400)
    spo = dm.SampleprepParameterOption.objects.filter(pk=paramopt_id)
    if not spo.count():
        return JsonResponse({'error': 'Could not find method, contact admin'}, status=400)
    spo.update(active=False)
    return JsonResponse({})


@staff_member_required
@login_required
def disable_sampleprep_method_version(request):
    pass


@staff_member_required
@login_required
def enable_sampleprep_method(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        paramopt_id = req['paramopt_id']
    except KeyError:
        return JsonResponse({'error': 'Bad request to enable sampleprep method, contact admin'},
                status=400)
    spo = dm.SampleprepParameterOption.objects.filter(pk=paramopt_id, active=False)
    if not spo.count():
        return JsonResponse({'error': 'Could not find method, contact admin'}, status=400)
    spo.update(active=True)
    return JsonResponse({})


@staff_member_required
@login_required
def enable_sampleprep_method_version(request):
    pass


@staff_member_required
@login_required
def delete_sampleprep_method(request):
    req = json.loads(request.body.decode('utf-8'))
    try:
        paramopt_id = req['paramopt_id']
    except KeyError:
        return JsonResponse({'error': 'Bad request to delete sampleprep method, contact admin'},
                status=400)
    spo = dm.SampleprepParameterOption.objects.filter(pk=paramopt_id)
    if not spo.count():
        return JsonResponse({'error': 'Could not find method, contact admin'}, status=400)
    if dm.SampleprepParameterValue.objects.filter(value_id=paramopt_id).exists():
        return JsonResponse({'error': 'Datasets exist mapped to this method, we cant delete it!'}, status=403)
    spo.delete()
    return JsonResponse({})


@staff_member_required
@login_required
def delete_sampleprep_method_version(request):
    pass


