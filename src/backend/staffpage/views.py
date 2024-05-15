import json

from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q

from kantele import settings
from rawstatus import models as rm
from rawstatus.views import run_singlefile_qc, query_all_qc_files
from datasets import models as dm
from jobs.jobutil import create_job


@staff_member_required
@require_GET
def show_staffpage(request):
    context = {'qc_instruments': {x['producer__pk']: x['producer__name'] for x in 
        rm.MSInstrument.objects.filter(producer__internal=True, active=True).values(
            'producer__pk', 'producer__name')}}
    return render(request, 'staffpage/staffpage.html', context)


@staff_member_required
@require_POST
def rerun_singleqc(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        sfid = int(data['sfid'])
    except (KeyError, ValueError):
        return JsonResponse({'state': 'error', 'msg': 'Something went wrong, contact admin'}, status=400)
    sfs = query_all_qc_files().filter(pk=sfid).select_related(
            'rawfile__producer__msinstrument__instrumenttype')
    if sfs.count() == 1:
        # Get user for analysis (first Operator which is staff)
        staff_ops = dm.Operator.objects.filter(user__is_staff=True)
        if staff_ops.exists():
            user_op = staff_ops.first()
        else:
            user_op = dm.Operator.objects.first()
        sf = sfs.get()
        # retrieve if needed
        if sf.purged and sf.deleted:
            if hasattr(sf, 'pdcbackedupfile') and sfile.pdcbackedupfile.success and not sfile.pdcbackedupfile.deleted:
                create_job('restore_from_pdc_archive', sf_id=sf.pk)
                run_singlefile_qc(sf.rawfile, sf, user_op)
                msg = f'Queued {sf.filename} QC raw for retrieval from archive and rerun'
                state = 'ok'
            else:
                msg = (f'QC file {sf.filename} is marked as deleted, but cannot be restored, '
                        'contact admin')
                state = 'error'
        else:
            run_singlefile_qc(sf.rawfile, sf, user_op)
            msg = f'Queued {sf.filename} QC raw for rerun'
            state = 'ok'
    else:
        msg = 'Something went wrong, could not get file to run QC on, contact admin'
        state = 'error'
    return JsonResponse({'msg': msg, 'state': state})


@staff_member_required
@require_POST
def rerun_qcs(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        assert type(data['instruments']) == list
        days_back = int(data['days'])
        instruments = [int(x) for x in data['instruments']]
        confirm_ok = data['confirm']
    except (KeyError, TypeError, ValueError, AssertionError):
        return JsonResponse({'state': 'error', 'msg': 'Something went wrong, contact admin'}, status=400)
    lastdate = (timezone.now() - timezone.timedelta(days_back)).date()
    # Filter QC files (in path, no dataset, claimed, date)
    sfs = query_all_qc_files().filter(rawfile__date__gte=lastdate).select_related(
            'rawfile__producer__msinstrument__instrumenttype')
    if confirm_ok:
        # Get user for analysis (first Operator which is staff)
        staff_ops = dm.Operator.objects.filter(user__is_staff=True)
        if staff_ops.exists():
            user_op = staff_ops.first()
        else:
            user_op = dm.Operator.objects.first()
        for sf in sfs:
            # FIXME maybe need to retrieve from archive
            run_singlefile_qc(sf.rawfile, sf, user_op)
        msg = f'Queued {sfs.count()} QC raw files for running'
        state = 'ok'
    else:
        msg = f'You have selected {sfs.count()} QC raw files, is that OK?'
        state = 'confirm'
    return JsonResponse({'msg': msg, 'state': state})


@login_required
@require_GET
def get_qc_files(request):
    query = Q()
    for searchterm in [x for x in request.GET.get('q', '').split(' ') if x != '']:
        subq = Q()
        subq |= Q(filename__icontains=searchterm)
        subq |= Q(rawfile__producer__name__icontains=searchterm)
        query &= subq
    filtered = query_all_qc_files().filter(query)
    if filtered.count() > 50:
        fns = {}
    else:
        fns = {x.pk: {'id': x.pk, 'name': x.filename} for x in filtered}
    return JsonResponse(fns)


def rerun_single_qc(request):
    return JsonResponse({'msg': msg, 'state': state})
