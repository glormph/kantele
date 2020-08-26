import re
import os
import json
from datetime import datetime
from django.http import (HttpResponseForbidden, HttpResponse, JsonResponse, HttpResponseNotFound, HttpResponseNotAllowed)
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from kantele import settings
from analysis import models as am
from analysis import jobs as aj
from datasets import models as dm
from rawstatus import models as rm
from home import views as hv
from jobs import jobs as jj
from jobs import models as jm


@login_required
def get_analysis_init(request):
    dsids = request.GET['dsids'].split(',')
    try:
        context = {'dsids': dsids}
    except:
        return HttpResponseForbidden()
    return render(request, 'analysis/analysis.html', context)


def check_fasta_release(request):
    dbmods = {'ensembl': am.EnsemblFasta, 'uniprot': am.UniProtFasta}
    dbstates = []
    for ftype in ['ensembl', 'uniprot']:
        isoforms = [True, False] if ftype == 'uniprot' else [False]
        for organism in settings.UP_ORGS:
            if ftype in request.GET and request.GET[ftype]:
                version = request.GET[ftype]
                frecords = dbmods[ftype].objects.select_related('libfile__sfile').filter(version=version, organism=organism)
                output = [{'db': ftype, 'version': version, 'state': False, 'organism': organism, 'isoforms': x} for x in isoforms]
                for frec in frecords:
                    if ftype == 'uniprot':
                        [x.update({'state': frec.libfile.sfile.checked}) for x in output if x['isoforms'] == frec.isoforms]
                    else:
                        [x.update({'state': frec.libfile.sfile.checked}) for x in output]
                dbstates.extend(output)
    return JsonResponse({'dbstates': dbstates})


def set_protein_database_lib(request):
    req = json.loads(request.body.decode('utf-8'))
    isoforms = 'isoforms' in req and req['isoforms']
    libfile = am.LibraryFile.objects.select_related('sfile').get(sfile__rawfile_id=req['fn_id'])
    dbmod = {'uniprot': am.UniProtFasta, 'ensembl': am.EnsemblFasta}[req['type']]
    kwargs = {'version': req['version'], 'libfile_id': libfile.id, 'organism': req['organism']}
    if req['type'] == 'uniprot':
        kwargs['isoforms'] = isoforms
    try:
        dbmod.objects.create(**kwargs)
    except IntegrityError as e:
        # THrown when DB complains about FK/uniqueness
        pass # FIXME
    else:
        jj.send_slack_message('New automatic fasta release done: {} - {} {}, version {}'.format(
            req['type'], req['organism'], 'with isoforms' if isoforms else '', req['version']), 'kantele')
    return HttpResponse()


@login_required
def get_allwfs(request):
    #dsids = request.GET['dsids'].split(',')
    allwfs = [{
        'id': x.id, 'nfid': x.nfworkflow_id, 'name': x.name, 
        'wftype': x.shortname.name,
        'versions': [{'name': wfv.update, 'id': wfv.id, 'latest': False,
                 'date': datetime.strftime(wfv.date, '%Y-%m-%d'), }
                 for wfv in am.NextflowWfVersion.objects.filter(nfworkflow_id=x.nfworkflow_id).order_by('pk')][::-1]
    }
#        'wf': get_workflow(request, x.id, dsids)} for x in
            for x in am.Workflow.objects.filter(public=True).order_by('pk')[::-1]]
    #versions[0]['latest'] = True
    order = [x['id'] for x in allwfs]
    allwfs = {x['id']: x for x in allwfs}
    return JsonResponse({'allwfs': allwfs, 'order': order})


@login_required
def get_datasets(request):
    dsids = request.GET['dsids'].split(',')
    response = {'error': False, 'errmsg': []}
    dsjobs = rm.FileJob.objects.exclude(job__state=jj.Jobstates.DONE).filter(
        storedfile__rawfile__datasetrawfile__dataset_id__in=dsids).select_related('job')
    info = {'jobs': [unijob for unijob in
                    {x.job.id: {'name': x.job.funcname, 'state': x.job.state}
                     for x in dsjobs}.values()]}
    files = rm.StoredFile.objects.select_related('rawfile').filter(
        rawfile__datasetrawfile__dataset_id__in=dsids)
    # FIXME default to refined mzmls if exist, now we enforce if exist for simplicity, make optional
    # FIXME if refined have been deleted, state it, maybe old auto-deleted and need to remake
    dbdsets = dm.Dataset.objects.filter(pk__in=dsids).select_related('quantdataset__quanttype')
    deleted = dbdsets.filter(deleted=True)
    if deleted.count():
        response['error'] = True
        response['errmsg'].append('Deleted datasets can not be analysed')
    dsetinfo = hv.populate_dset(dbdsets, request.user, showjobs=False, include_db_entry=True)
    for dsid, dsdetails in dsetinfo.items():
        dset = dsdetails.pop('dbentry')
        dsdetails.update({'details': hv.fetch_dset_details(dset)})
        try:
            dsdetails['details']['qtype'] = dset.quantdataset.quanttype.name
            dsdetails['details']['qtypeshort'] = dset.quantdataset.quanttype.shortname
        except dm.QuantDataset.DoesNotExist:
            response['error'] = True
            response['errmsg'].append('Dataset with runname {} has no quant details, please fill in sample prep fields'.format(dsdetails['run']))
        else:
            # FIXME TODO Pick live files from pwiz sets? Or mandate?
            dsfiles = files.filter(rawfile__datasetrawfile__dataset_id=dsid, checked=True, deleted=False, purged=False)
            nrneededfiles = dsdetails['details']['nrstoredfiles']['raw']
            refineddsfiles = dsfiles.filter(mzmlfile__refined=True)
            if refineddsfiles.count() == nrneededfiles:
                dsfiles = refineddsfiles
            else:
                dsfiles = dsfiles.filter(mzmlfile__refined=False)
            if dsfiles.count() != nrneededfiles:
                response['error'] = True
                response['errmsg'].append('Need to create or finish refining mzML files first in dataset {}'.format(dsdetails['run']))
            dsdetails['model'] = {'set': False}
            if 'lex' in dset.quantdataset.quanttype.name:
                dsdetails['details']['channels'] = {
                    ch.channel.channel.name: ch.projsample.sample for ch in
                    dm.QuantChannelSample.objects.select_related(
                        'projsample', 'channel__channel').filter(dataset_id=dsid)}
                dsdetails['model']['denoms'] = {
                    x: False for x in dsdetails['details']['channels']}
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'fr': '', 'setname': '', 'sample': ''} for x in dsfiles]
            else:
                dsdetails['details']['channels'] = {}
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'fr': '', 'sample': x.rawfile.datasetrawfile.quantsamplefile.projsample.sample} for x in dsfiles.select_related('rawfile__datasetrawfile__quantsamplefile__projsample')]
                [x.update({'setname': x['sample']}) for x in dsdetails['files']]
    # FIXME labelfree quantsamplefile without sample prep error msg
    response['dsets'] = dsetinfo
    return JsonResponse(response)


@login_required
def get_workflow_versioned(request):
    try:
        wf = am.NextflowWfVersion.objects.get(pk=request.GET['wfvid'])
    except am.NextflowWfVersion.DoesNotExist:
        return HttpResponseNotFound()
    params = wf.paramset.psetparam_set.select_related('param')
    files = wf.paramset.psetfileparam_set.select_related('param')
    multifiles = wf.paramset.psetmultifileparam_set.select_related('param')
    fixedfiles = wf.paramset.psetpredeffileparam_set.select_related('libfile__sfile')
    ftypes = [x['param__filetype_id'] for x in files.values('param__filetype_id').distinct()]
    ftypes.extend([x['param__filetype_id'] for x in multifiles.values('param__filetype_id').distinct()])
    ftypes = set(ftypes)
    selectable_files = [x for x in am.LibraryFile.objects.select_related('sfile__filetype').filter(
        sfile__filetype__in=ftypes)]
    userfiles = [x for x in rm.UserFile.objects.select_related('sfile__filetype').filter(
        sfile__filetype__in=ftypes)]
    selectable_files.extend(userfiles)
    resp = {
            'analysisapi': wf.kanteleanalysis_version,
            'flags': [{'nf': f.param.nfparam, 'name': f.param.name} 
                for f in params.filter(param__ptype='flag', param__visible=True)],
            'numparams': [{'nf': p.param.nfparam, 'name': p.param.name}
                for p in params.filter(param__ptype='number')],
            'multicheck': [{'nf': p.param.nfparam, 'name': p.param.name,
                'opts': {po.value: po.name for po in p.param.paramoption_set.all()}}
                for p in params.filter(param__ptype='multi', param__visible=True)],
            'fileparams': [{'name': f.param.name, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 
                'allow_resultfile': f.allow_resultfiles} for f in files],
            'multifileparams': [{'name': f.param.name, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 
                'allow_resultfile': f.allow_resultfiles} for f in multifiles],
            'fixedfileparams': [{'name': f.param.name, 'nf': f.param.nfparam,
                'fn': f.libfile.sfile.filename,
                'id': f.libfile.sfile.id,
                'desc': f.libfile.description}
                for f in fixedfiles],
            'libfiles': {ft: [{'id': x.sfile.id, 'desc': x.description,
                'name': x.sfile.filename}
                for x in selectable_files if x.sfile.filetype_id == ft] for ft in ftypes}
    }
    # Get files from earlier analyses on same datasets
    # double filtering gets first all DsS records that that have an analysis with ANY of the records,
    # and then strip out:
    #    - with analysis that also have MORE datasets
    #    - analysis that have a subset of datasets
    dsids = [int(x) for x in request.GET['dsids'].split(',')]
    superset_analysis = am.DatasetSearch.objects.filter(analysis__datasetsearch__dataset_id__in=dsids).exclude(dataset__id__in=dsids).values('analysis')
    qset_analysis = am.Analysis.objects.filter(datasetsearch__dataset__in=dsids).exclude(pk__in=superset_analysis)
    for dsid in dsids:
        qset_analysis = qset_analysis.filter(datasetsearch__dataset_id=dsid)
    resp['prev_resultfiles'] = [{'id': x.sfile.id, 'name': x.sfile.filename, 
        'analysisname': x.analysis.name, 
        'analysisdate': datetime.strftime(x.analysis.date, '%Y-%m-%d')}
        for x in am.AnalysisResultFile.objects.filter(
            analysis__in=qset_analysis.distinct()).select_related('analysis')]
    return JsonResponse({'wf': resp})


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
        return JsonResponse({'error': 'Deleted datasets cannot be analyzed'})
    analysis = am.Analysis(name=req['analysisname'], user_id=request.user.id)
    analysis.save()
    am.DatasetSearch.objects.bulk_create([am.DatasetSearch(dataset_id=x, analysis=analysis) for x in req['dsids']])
    params = {'singlefiles': {nf: fnid for nf, fnid in req['singlefiles'].items()},
            'multifiles': {nf: fnids for nf, fnids in req['multifiles'].items()},
            'params': [multip for p, vals in req['params'].pop('multi').items() for multip in [p, ';'.join(vals)]]}
    params['params'].extend([y for x in req['params'].values() for y in x])
    if 'sampletable' in req and len(req['sampletable']):
        params['sampletable'] = req['sampletable']
    arg_dsids = [int(x) for x in req['dsids']]
    wf = am.Workflow.objects.select_related('shortname').get(pk=req['wfid'])
    if wf.shortname.name != 'LC':
        fname = 'run_nf_search_workflow'
        strips = {}
        for dsid in req['dsids']:
            strip = req['strips'][dsid]
            if strip == 'unknown_plate':
                strips[dsid] = strip
            elif strip:
                strip = re.sub('[a-zA-Z]', '', strip)
                strips[dsid] = '-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in strip.split('-')])
            else:
                strips[dsid] = False  # FIXME does that work?
                # FIXME when strip is False (as passed from javascript) we need to do something, eg long gradients 
        data_args = {'platenames': strips, 'fractions': req['fractions'], 'setnames': req['setnames']}
    else:
        fname = 'run_nf_lc_workflow'
        data_args = {'dset_ids': req['dsids']}
    param_args = {'wfv_id': req['nfwfvid'], 'inputs': params}
    jobcheck = jj.check_existing_search_job(fname, req['wfid'], **{'dset_ids': arg_dsids, **data_args, **param_args})
    if jobcheck:
        return JsonResponse({'error': 'This analysis already exists', 'link': '/?tab=searches&anids={}'.format(jobcheck.nextflowsearch.id)})
    job = jj.create_job(fname, **{'analysis_id': analysis.id, **data_args, **param_args})
    aj.create_nf_search_entries(analysis, req['wfid'], req['nfwfvid'], job.id)
    return JsonResponse({'error': False})


@login_required
def undelete_analysis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    try:
        analysis = am.Analysis.objects.select_related('nextflowsearch__job').get(nextflowsearch__id=req['item_id'])
    except am.Analysis.DoesNotExist:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    if not analysis.deleted:
        return JsonResponse({'error': 'Analysis is not deleted, cant undelete it'}, status=403)
    if analysis.user == request.user or request.user.is_staff:
        analysis.deleted = False
        analysis.save()
        am.AnalysisDeleted.objects.filter(analysis=analysis).delete()
        return JsonResponse({})
    else:
        return JsonResponse({'error': 'User is not authorized to undelete this analysis'}, status=403)


@login_required
def delete_analysis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    try:
        analysis = am.Analysis.objects.select_related('nextflowsearch__job').get(nextflowsearch__id=req['item_id'])
    except am.Analysis.DoesNotExist:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    if analysis.deleted:
        return JsonResponse({'error': 'Analysis is already deleted'}, status=403)
    if analysis.user == request.user or request.user.is_staff:
        if not analysis.deleted:
            analysis.deleted = True
            analysis.save()
            del_record = am.AnalysisDeleted(analysis=analysis)
            del_record.save()
            ana_job = analysis.nextflowsearch.job
            if ana_job.state not in jj.Jobstates.DONE:
                ana_job.state = jj.Jobstates.CANCELED
                ana_job.save()
        return JsonResponse({})
    else:
        return JsonResponse({'error': 'User is not authorized to delete this analysis'}, status=403)


@login_required
def purge_analysis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    elif not request.user.is_staff:
        return JsonResponse({'error': 'Only admin is authorized to purge analysis'}, status=403)
    req = json.loads(request.body.decode('utf-8'))
    try:
        analysis = am.Analysis.objects.get(nextflowsearch__id=req['item_id'])
    except am.Analysis.DoesNotExist:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    if not analysis.deleted:
        return JsonResponse({'error': 'Analysis is not deleted, cannot purge'}, status=403)
    analysis.purged = True
    analysis.save()
    jj.create_job('purge_analysis', analysis_id=analysis.id)
    jj.create_job('delete_empty_directory',
            sf_ids=[x.sfile_id for x in analysis.analysisresultfile_set.all()])
    return JsonResponse({})


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
