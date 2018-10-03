import re
import os
import json
from datetime import datetime
from django.http import (HttpResponseForbidden, HttpResponse, JsonResponse, HttpResponseNotFound)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Subquery

from kantele import settings
from analysis import models as am
from datasets import models as dm
from rawstatus import models as rm
from home import views as hv
from jobs import jobs as jj
from jobs import models as jm


@login_required
def get_analysis_init(request):
    wfid = request.GET['wfid'] if 'wfid' in request.GET else 0
    dsids = request.GET['dsids'].split(',')
    try:
        context = {'dsids': dsids,
                   'wfid': wfid,
                   }
    except:
        return HttpResponseForbidden()
    return render(request, 'analysis/analysis.html', context)


@login_required
def get_allwfs(request):
    allwfs = {x.id: {'id': x.id, 'nfid': x.nfworkflow_id, 'name': x.name} for x in
              am.Workflow.objects.filter(public=True)}
    return JsonResponse({'allwfs': allwfs})


@login_required
def get_datasets(request):
    dsids = request.GET['dsids'].split(',')
    response = {'isoquants': [], 'error': False, 'errmsg': []}
    dsjobs = rm.FileJob.objects.exclude(job__state=jj.Jobstates.DONE).filter(
        storedfile__rawfile__datasetrawfile__dataset_id__in=dsids).select_related('job')
    info = {'jobs': [unijob for unijob in
                    {x.job.id: {'name': x.job.funcname, 'state': x.job.state}
                     for x in dsjobs}.values()]}
    files = rm.StoredFile.objects.select_related('rawfile').filter(
        rawfile__datasetrawfile__dataset_id__in=dsids)
    nrstoredfiles, sfinfo = hv.get_nr_raw_mzml_files(files, info)
    # FIXME default to refined mzmls if exist, now we enforce if exist for simplicity, make optional
    dbdsets = dm.Dataset.objects.filter(pk__in=dsids).select_related('quantdataset__quanttype')
    deleted = dbdsets.filter(deleted=True)
    if deleted.count():
        response['error'] = True
        response['errmsg'].append('Deleted datasets can not be analysed')
    dsetinfo = hv.populate_dset(dbdsets, request.user, showjobs=False, include_db_entry=True)
    for dsid, dsdetails in dsetinfo.items():
        dset = dsdetails.pop('dbentry')
        dsdetails['filesaresets'] = False
        dsdetails.update({'details': hv.fetch_dset_details(dset)})
        if dsdetails['details']['mzmlable'] or dsdetails['details']['refinable'] in ['blocked', 'partly']:
            response['error'] = True
            response['errmsg'].append('Need to create or finish refining mzML files first in dataset {}'.format(dsdetails['run']))
        dsdetails['model'] = {'set': False}
        try:
            dsdetails['details']['qtype'] = dset.quantdataset.quanttype.name
        except dm.QuantDataset.DoesNotExist:
            response['error'] = True
            response['errmsg'].append('Dataset with runname {} has no quant details, please fill in sample prep fields'.format(dsdetails['run']))
        else:
            dsfiles = files.filter(rawfile__datasetrawfile__dataset_id=dsid)
            refineddsfiles = dsfiles.filter(filetype_id=settings.REFINEDMZML_SFGROUP_ID)
            if refineddsfiles.count():
                dsfiles = refineddsfiles
            else:
                dsfiles = dsfiles.filter(filetype_id=settings.MZML_SFGROUP_ID)
            if 'lex' in dset.quantdataset.quanttype.name:
                dsdetails['details']['channels'] = {
                    ch.channel.channel.name: ch.sample for ch in
                    dm.QuantChannelSample.objects.select_related(
                        'channel__channel').filter(dataset_id=dsid)}
                dsdetails['model']['denoms'] = {
                    x: False for x in dsdetails['details']['channels']}
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'fr': '', 'setname': '', 'sample': ''} for x in dsfiles]
            else:
                dsdetails['details']['channels'] = {}
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'matchedFr': '', 'fr': '', 'sample': x.rawfile.datasetrawfile.quantsamplefile.sample} for x in dsfiles.select_related('rawfile__datasetrawfile__quantsamplefile')]
                [x.update({'setname': x['sample']}) for x in dsdetails['files']]
    # FIXME labelfree quantsamplefile without sample prep error msg
    response['dsets'] = dsetinfo
    return JsonResponse(response)


@login_required
def get_workflow(request):
    try:
        wf = am.Workflow.objects.filter(public=True).get(pk=request.GET['wfid'])
    except am.Workflow.DoesNotExist:
        return HttpResponseNotFound()
    params = wf.workflowparam_set.all().select_related('param')
    files = wf.workflowfileparam_set.select_related('param')
    fixedfiles = wf.workflowpredeffileparam_set.select_related('libfile__sfile')
    flags = params.filter(param__ptype='flag')
    ftypes = files.values('param__filetype__name').distinct()
    libfiles = [x for x in am.LibraryFile.objects.select_related('sfile__filetype').filter(
        sfile__filetype__in=Subquery(files.values('param__filetype')))]
    versions = [{'name': wfv.update, 'id': wfv.id, 'latest': False,
                 'date': datetime.strftime(wfv.date, '%Y-%m-%d')} for wfv in
                am.NextflowWfVersion.objects.filter(nfworkflow_id=wf.nfworkflow_id)][::-1]
    versions[0]['latest'] = True
    resp = {
        'wf': {
            'flags': {f.param.nfparam: f.param.name for f in flags},
            'files': [{'name': f.param.name, 'nf': f.param.nfparam,
                       'ftype': f.param.filetype.name} for f in files],
            'fixedfiles': [{'name': f.param.name, 'nf': f.param.nfparam,
                            'fn': f.libfile.sfile.filename,
                            'id': f.libfile.sfile.id,
                            'desc': f.libfile.description}
                           for f in fixedfiles],
             'wftype': wf.shortname.name,
        },
        'versions': versions,
        'files': {ft['param__filetype__name']: [{'id': x.sfile.id, 'desc': x.description,
                                           'name': x.sfile.filename}
                                          for x in libfiles
                                          if x.sfile.filetype.name == ft['param__filetype__name']]
                  for ft in ftypes}
    }
    return JsonResponse(resp)


@login_required
def show_analysis_log(request, nfs_id):
    try:
        nfs = am.NextflowSearch.objects.get(pk=nfs_id)
    except am.NextflowSearch.DoesNotExist:
        return HttpResponseNotFound()
    return HttpResponse('\n'.join(json.loads(nfs.analysis.log)), content_type="text/plain")


@login_required
def start_analysis(request):
    # queue nextflow
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    req = json.loads(request.body.decode('utf-8'))
    if dm.Dataset.objects.filter(pk__in=req['dsids'], deleted=True):
    	return JsonResponse({'state': 'error', 'msg': 'Deleted datasets cannot be analyzed'})
    analysis = am.Analysis(name=req['analysisname'], user_id=request.user.id)
    analysis.save()
    strips = {}
    for dsid in req['dsids']:
        strip = req['strips'][dsid]
        if strip:
            strip = re.sub('[a-zA-Z]', '', strip)
            strips[dsid] = '-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in strip.split('-')])
        else:
            strips[dsid] = False  # FIXME does that work?
            # FIXME when strip is False (as passed from javascript) we need to do something, eg long gradients 
    params = {'singlefiles': {nf: fnid for nf, fnid in req['files'].items()},
              'params': [y for x in req['params'].values() for y in x]}
    # FIXME run_ipaw_nextflow rename job
    fname = 'run_ipaw_nextflow'
    arg_dsids = [int(x) for x in req['dsids']]
    # FIXME do not check the analysis_id!
    # FIXME setnames have changed, is that ok?
    jobcheck = jj.check_existing_search_job(fname, arg_dsids, strips, req['fractions'], req['setnames'], req['wfid'], req['nfwfvid'], params)
    if jobcheck:
    	return JsonResponse({'state': 'error', 'msg': 'This analysis already exists', 'link': '/?tab=searches&search_id={}'.format(jobcheck.nextflowsearch.id)})
    job = jj.create_dataset_job(fname, arg_dsids, strips, req['fractions'], req['setnames'], analysis.id, req['wfid'], req['nfwfvid'], params)
    create_nf_search_entries(analysis, req['wfid'], req['nfwfvid'], job.id)
    return JsonResponse({'state': 'ok'})


@login_required
def serve_analysis_file(request, file_id):
    try:
        sf = get_servable_files(am.AnalysisResultFile.objects.select_related(
            'sfile__servershare')).get(pk=file_id)
    except am.AnalysisResultFile.DoesNotExist:
        return HttpResponseForbidden()
    resp = HttpResponse()
    resp['X-Accel-Redirect'] = os.path.join(settings.NGINX_ANALYSIS_REDIRECT, sf.sfile.path, sf.sfile.filename)
    return resp


def get_servable_files(resultfiles):
    return resultfiles.filter(sfile__filename__in=settings.SERVABLE_FILENAMES)


def create_nf_search_entries(analysis, wf_id, nfv_id, job_id):
    try:
        nfs = am.NextflowSearch.objects.get(analysis=analysis)
    except am.NextflowSearch.DoesNotExist:
        nfs = am.NextflowSearch(nfworkflow_id=nfv_id, job_id=job_id,
                                    workflow_id=wf_id, analysis=analysis)
        nfs.save()


def write_analysis_log(logline, analysis_id):
    analysis = am.Analysis.objects.get(pk=analysis_id)
    log = json.loads(analysis.log)
    log.append(logline)
    analysis.log = json.dumps(log)
    analysis.save()


def append_analysis_log(request):
    req = json.loads(request.body.decode('utf-8'))
    write_analysis_log(req['message'], req['analysis_id'])
    return HttpResponse()
