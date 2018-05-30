import re
import json
from datetime import datetime
from django.http import (HttpResponseForbidden, HttpResponse, JsonResponse)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Subquery

from kantele import settings
from analysis import models as am
from datasets import models as dm
from home import views as hv
from jobs import jobs as jj


@login_required
def get_analysis_init(request):
    #nfwfid = request.GET['nfid']
    wfid = request.GET['wfid']
    dsids = request.GET['dsids'].split(',')
    wf = am.Workflow.objects.get(pk=wfid)
    wftype = wf.shortname
    wfversion_id = am.NextflowWfVersion.objects.filter(nfworkflow_id=wf.nfworkflow_id).last().id
    try:
        context = {'dsids': dsids,
                   'wfid': wfid,
                   'wfv': wfversion_id,
                   'wftype': wftype,
                   }
    except:
        return HttpResponseForbidden()
    return render(request, 'analysis/analysis.html', context)


@login_required
def get_allwfs(request):
    allwfs = {x.id: {'id': x.id, 'nfid': x.nfworkflow_id, 'name': x.name} for x in
              am.Workflow.objects.all()}
    return JsonResponse({'allwfs': allwfs})


@login_required
def get_datasets(request):
    dsids = request.GET['dsids'].split(',')
    # FIXME quanttype not exist --> error! when sample prep is not filled in
    # Or do not allow selection of those in prev view
    dbdsets = dm.Dataset.objects.filter(pk__in=dsids).select_related('quantdataset__quanttype')
    dsetinfo = hv.populate_dset(dbdsets, request.user, showjobs=False, include_db_entry=True)
    for dsid in dsetinfo:
        dset = dsetinfo[dsid].pop('dbentry')
        dsetinfo[dsid].update({'details': hv.fetch_dset_details(dset)})
        dsetinfo[dsid]['model'] = {'set': False}
        dsetinfo[dsid]['details']['qtype'] = dset.quantdataset.quanttype.name
        if 'lex' in dset.quantdataset.quanttype.name:
            dsetinfo[dsid]['details']['channels'] = {
                ch.channel.channel.name: ch.sample for ch in
                dm.QuantChannelSample.objects.select_related(
                    'channel__channel').filter(dataset_id=dsid)}
            dsetinfo[dsid]['model']['denoms'] = {
                x: False for x in dsetinfo[dsid]['details']['channels']}
        else:
            dsetinfo[dsid]['details']['channels'] = {}

    return JsonResponse({'dsets': dsetinfo, 'isoquants': []})


@login_required
def get_workflow(request):
    wf = am.Workflow.objects.get(pk=request.GET['wfid'])
    params = wf.workflowparam_set.all().select_related('param')
    files = wf.workflowfileparam_set.select_related('param')
    fixedfiles = wf.workflowpredeffileparam_set.select_related('libfile__sfile')
    flags = params.filter(param__ptype='flag')
    values = params.filter(param__ptype='value')
    ftypes = files.values('param__filetype')
    libfiles = [x for x in am.LibraryFile.objects.select_related('sfile').filter(
        sfile__filetype__in=Subquery(files.values('param__filetype')))]
    versions = [{'name': wfv.update, 'id': wfv.id,
                 'date': datetime.strftime(wfv.date, '%Y-%m-%d')} for wfv in
                am.NextflowWfVersion.objects.all()][::-1]
    resp = {
        'wf': {
            'flags': {f.param.nfparam: f.param.name for f in flags},
            'files': [{'name': f.param.name, 'nf': f.param.nfparam,
                       'ftype': f.param.filetype} for f in files],
            'fixedfiles': [{'name': f.param.name, 'nf': f.param.nfparam,
                            'fn': f.libfile.sfile.filename,
                            'id': f.libfile.sfile.id,
                            'desc': f.libfile.description}
                           for f in fixedfiles],
        },
        'versions': versions,
        'files': {ft['param__filetype']: [{'id': x.sfile.id, 'desc': x.description,
                                           'name': x.sfile.filename}
                                          for x in libfiles
                                          if x.sfile.filetype == ft['param__filetype']]
                  for ft in ftypes}
    }
    return JsonResponse(resp)


@login_required
def start_analysis(request):
    # queue nextflow
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    req = json.loads(request.body.decode('utf-8'))
    analysis = am.Analysis(name=req['analysisname'], user_id=request.user.id)
    analysis.save()
    dsids = [x for x in req['setnames']]
    setnames = [req['setnames'][x] for x in dsids]
    strips = []
    for dsid in dsids:
        strip = req['strips'][dsid]
        if strip:
            strip = re.sub('[a-zA-Z]', '', strip)
            strips.append('-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in strip.split('-')]))
        else:
            pass # FIXME when strip is False (as passed from javascript) we need to do something, eg long gradients etc
    # FIXME fractions are now hardcoded regex, make this in JS, and an option
    # for not using fraction
    params = {'singlefiles': {nf: fnid for nf, fnid in req['files'].items()},
              'params': [y for x in req['params'].values() for y in x]}
    # FIXME run_ipaw_nextflow rename job
    job = jj.create_dataset_job('run_ipaw_nextflow', [int(x) for x in dsids], strips, setnames, analysis.id, req['nfwfvid'], params)
    return JsonResponse({})
