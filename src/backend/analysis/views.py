import re
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import uuid4

from django.utils import timezone
from django.http import (HttpResponseForbidden, HttpResponse, JsonResponse,
        HttpResponseNotFound)
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render
from django.db.models import Q

from kantele import settings
from analysis import models as am
from analysis import jobs as aj
from datasets import models as dm
from rawstatus import models as rm
from home import views as hv
from jobs import jobs as jj
from jobs import views as jv
from jobs import models as jm


@login_required
@require_GET
def get_analysis_init(request):
    dsids = request.GET['dsids'].split(',')
    try:
        context = {'dsids': dsids, 'analysis': False}
    except:
        return HttpResponseForbidden()
    return render(request, 'analysis/analysis.html', context)


@login_required
def load_analysis_resultfiles(request, anid):
    try:
        ana = am.Analysis.objects.get(pk=anid)
    except am.Analysis.DoesNotExist:
        return JsonResponse({'error': 'Base analysis not found'}, status=403)
    analysis_date = datetime.strftime(ana.date, '%Y-%m-%d')
    resultfiles = [{'id': x.sfile_id, 
        'name': '{} - Result of {} ({})'.format(x.sfile.filename, aj.get_ana_fullname(ana), analysis_date)}
        for x in ana.analysisresultfile_set.all()]
    return JsonResponse({'analysisname': aj.get_ana_fullname(ana), 'date': analysis_date, 'fns': resultfiles})


@login_required
def load_base_analysis(request, wfversion_id, baseanid):
    """Find analysis to base current analysis on, for either copying parameters,
    complementing with new sample sets, or a rerun from PSM table.

    FIXME: This method, and the belonging DB model for base analysis is coupled to the DDA
    MS proteomics pipeline, and therefore not very general, due to the complement and rerun
    functionality. Maybe find a way around that, breaking those off from regular base analysis.
    """
    dsids = [int(x) for x in request.GET['dsids'].split(',')]
    try:
        new_pset_id = am.NextflowWfVersion.objects.values('paramset_id').get(pk=wfversion_id)['paramset_id']
    except am.NextflowWfVersion.DoesNotExist:
        return JsonResponse({'error': 'Workflow for applying base analysis not found'}, status=403)
    try:
        ana = am.Analysis.objects.select_related('nextflowsearch').get(pk=baseanid)
    except am.Analysis.DoesNotExist:
        return JsonResponse({'error': 'Base analysis not found'}, status=403)
    analysis = {
            'analysis_id': ana.pk,
            'dsets_identical': set(dss.dataset_id for dss in ana.datasetsearch_set.all()) == set(dsids),
            'mzmldef': False,
            'flags': [],
            'multicheck': [],
            'inputparams': {},
            'multifileparams': {},
            'fileparams': {},
            'isoquants': {},
            'resultfiles': [],
            }
    for ap in ana.analysisparam_set.filter(param__psetparam__pset_id=new_pset_id):
        if ap.param.ptype == 'flag' and ap.value:
            analysis['flags'].append(ap.param.id)
        elif ap.param.ptype == 'multi':
            analysis['multicheck'].extend(['{}___{}'.format(ap.param.id, str(x)) for x in ap.value])
        elif ap.param.ptype == 'number':
            analysis['inputparams'][ap.param_id] = ap.value
        elif ap.param.ptype == 'text':
            analysis['inputparams'][ap.param_id] = ap.value
    pset = ana.nextflowsearch.nfworkflow.paramset
    multifiles = {x.param_id for x in pset.psetmultifileparam_set.all()}
    for afp in ana.analysisfileparam_set.filter(param__psetfileparam__pset_id=new_pset_id):
        if afp.param_id in multifiles:
            try:
                fnr = max(analysis['multifileparams'][afp.param_id].keys()) + 1
            except KeyError:
                fnr = 0
                analysis['multifileparams'][afp.param_id] = {}
            analysis['multifileparams'][afp.param_id][fnr] = afp.sfile_id
        else:
            analysis['fileparams'][afp.param_id] = afp.sfile_id
    if hasattr(ana, 'analysismzmldef') and am.PsetComponent.objects.filter(
            pset_id=new_pset_id, component__name='mzmldef'):
        analysis['mzmldef'] = ana.analysismzmldef.mzmldef
    dsets = {ads.dataset_id: {'setname': ads.setname.setname, 'regex': ads.regex} for ads in ana.analysisdatasetsetname_set.all()}
    try:
        sampletables = am.AnalysisSampletable.objects.get(analysis=ana).samples
    except am.AnalysisSampletable.DoesNotExist:
        sampletables = {}
    analysis['isoquants'] = get_isoquants(ana, sampletables)
    try:
        baseana_dbrec = am.AnalysisBaseanalysis.objects.get(analysis=ana)
    except am.AnalysisBaseanalysis.DoesNotExist:
        pass
    else:
        dsets.update(baseana_dbrec.shadow_dssetnames)
        analysis['isoquants'].update(baseana_dbrec.shadow_isoquants)
    resultfiles = [{'id': x.sfile_id, 
        'name': '{} - Result of {} ({})'.format(x.sfile.filename, aj.get_ana_fullname(ana), datetime.strftime(ana.date, '%Y-%m-%d'))}
        for x in ana.analysisresultfile_set.all()]
    return JsonResponse({'base_analysis': analysis, 'datasets': dsets, 'resultfiles': resultfiles})



@login_required
def get_analysis(request, anid):
    try:
        ana = am.Analysis.objects.get(nextflowsearch__pk=anid)
    except am.Analysis.DoesNotExist:
        return HttpResponseNotFound()
    if ana.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden()
    analysis = {
            'analysis_id': ana.pk,
            'editable': ana.nextflowsearch.job.state in [jj.Jobstates.WAITING, jj.Jobstates.CANCELED, jj.Jobstates.ERROR],
            'wfversion_id': ana.nextflowsearch.nfworkflow_id,
            'wfid': ana.nextflowsearch.workflow_id,
            'mzmldef': False,
            'analysisname': ana.name,
            'flags': [],
            'multicheck': [],
            'inputparams': {},
            'multifileparams': {},
            'fileparams': {},
            'isoquants': {},
            'added_results': {},
            'base_analysis': False,
            }
    for ap in ana.analysisparam_set.all():
        if ap.param.ptype == 'flag' and ap.value:
            analysis['flags'].append(ap.param.id)
        elif ap.param.ptype == 'multi':
            analysis['multicheck'].extend(['{}___{}'.format(ap.param.id, str(x)) for x in ap.value])
        elif ap.param.ptype == 'text':
            analysis['inputparams'][ap.param_id] = ap.value
        elif ap.param.ptype == 'number':
            analysis['inputparams'][ap.param_id] = ap.value
    pset = ana.nextflowsearch.nfworkflow.paramset
    multifiles = {x.param_id for x in pset.psetmultifileparam_set.all()}

    dsids = [x.dataset_id for x in ana.datasetsearch_set.all()]
    # Parse base analysis if any
    ana_base = am.AnalysisBaseanalysis.objects.select_related('base_analysis__nextflowsearch').filter(analysis_id=ana.id)
    if ana_base.exists():
        ana_base = ana_base.get()
        base_dsids = [x.dataset_id for x in ana_base.base_analysis.datasetsearch_set.all()]
        analysis['base_analysis'] = {
                'resultfiles':  [{'id': x.sfile_id, 'name': x.sfile.filename} for x in ana_base.base_analysis.analysisresultfile_set.all()],
                'selected': ana_base.base_analysis_id,
                'typedname': '{} - {} - {} - {} - {}'.format(aj.get_ana_fullname(ana_base.base_analysis),
                ana_base.base_analysis.nextflowsearch.workflow.name, ana_base.base_analysis.nextflowsearch.nfworkflow.update,
                ana_base.base_analysis.user.username, datetime.strftime(ana_base.base_analysis.date, '%Y%m%d')),
                'isComplement': ana_base.is_complement,
                'runFromPSM': ana_base.rerun_from_psms,
                'dsets_identical': set(base_dsids) == set(dsids),
                }
        ana_base_resfiles = {x['id'] for x in analysis['base_analysis']['resultfiles']}
    else:
        ana_base_resfiles = set()
    # Parse input files, files from other analysis may need that other analysis included
    superset_analysis = am.DatasetSearch.objects.filter(analysis__datasetsearch__dataset_id__in=dsids).exclude(dataset__id__in=dsids).values('analysis')
    qset_analysis = am.Analysis.objects.filter(datasetsearch__dataset__in=dsids,
            deleted=False).exclude(pk__in=superset_analysis)
    for dsid in dsids:
        qset_analysis = qset_analysis.filter(datasetsearch__dataset_id=dsid)
    prev_resultfiles = {x.sfile_id for x in am.AnalysisResultFile.objects.filter(
            analysis__in=qset_analysis.distinct())}
    for afp in ana.analysisfileparam_set.all():
        if (hasattr(afp.sfile, 'analysisresultfile') and not hasattr(afp.sfile, 'libraryfile')
                and not afp.sfile_id in prev_resultfiles and not afp.sfile_id in ana_base_resfiles
                and afp.sfile.analysisresultfile.analysis_id not in analysis['added_results']):
            arf = afp.sfile.analysisresultfile
            arf_date = datetime.strftime(arf.analysis.date, '%Y-%m-%d')
            arf_fns = [{'id': x.sfile_id, 
                'name': '{} - Result of {} ({})'.format(x.sfile.filename, aj.get_ana_fullname(arf.analysis), arf_date)}
                for x in arf.analysis.analysisresultfile_set.all()]
            analysis['added_results'][arf.analysis_id] = {'analysisname': aj.get_ana_fullname(arf.analysis), 'date': arf_date, 'fns': arf_fns}

        if afp.param_id in multifiles:
            try:
                fnr = max(analysis['multifileparams'][afp.param_id].keys()) + 1
            except KeyError:
                fnr = 0
                analysis['multifileparams'][afp.param_id] = {}
            analysis['multifileparams'][afp.param_id][fnr] = afp.sfile_id
        else:
            analysis['fileparams'][afp.param_id] = afp.sfile_id
    if hasattr(ana, 'analysismzmldef'):
        analysis['mzmldef'] = ana.analysismzmldef.mzmldef
    try:
        sampletables = am.AnalysisSampletable.objects.get(analysis=ana).samples
    except am.AnalysisSampletable.DoesNotExist:
        sampletables = {}
    analysis['isoquants'] = get_isoquants(ana, sampletables)
    context = {
            'dsids': dsids,
            'analysis': analysis,
            }
    return render(request, 'analysis/analysis.html', context)


@require_GET
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
@require_GET
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


def get_dataset_files(dsid, use_refined):
    dsfiles = rm.StoredFile.objects.select_related('rawfile').filter(
        rawfile__datasetrawfile__dataset_id=dsid, checked=True, deleted=False, purged=False)
    refineddsfiles = dsfiles.filter(mzmlfile__refined=True)
    if use_refined and refineddsfiles.count() == dsfiles.filter(mzmlfile__isnull=True).count():
        dsfiles = refineddsfiles
    else:
        # TODO this gets only mzml files from the dataset:
        # If were going to pick other files by type we need to store that also in DB
        dsfiles = dsfiles.filter(mzmlfile__refined=False)
    return dsfiles


@login_required
@require_GET
def get_base_analyses(request):
    if 'q' in request.GET:
        query = Q()
        searchterms = request.GET['q'].split()
        for st in searchterms:
            subquery = Q(name__icontains=st)
            subquery |= Q(nextflowsearch__workflow__shortname__name__icontains=st)
            query &= subquery
        resp = {}
        for x in am.Analysis.objects.select_related('nextflowsearch').filter(query,
                nextflowsearch__isnull=False, deleted=False):
            resp[x.id] = {'id': x.id, 'name': '{} - {} - {} - {} - {}'.format(aj.get_ana_fullname(x),
                x.nextflowsearch.workflow.name, x.nextflowsearch.nfworkflow.update,
                x.user.username, datetime.strftime(x.date, '%Y%m%d'))}
        return JsonResponse(resp)
    else:
        return JsonResponse({'error': 'Need to specify search string to base analysis search'})


@login_required
@require_GET
def get_datasets(request):
    """Fetches datasets to analysis"""
    dsids = request.GET['dsids'].split(',')
    anid = int(request.GET['anid'])
    response = {'error': False, 'errmsg': []}
    dsjobs = rm.FileJob.objects.exclude(job__state=jj.Jobstates.DONE).filter(
        storedfile__rawfile__datasetrawfile__dataset_id__in=dsids).select_related('job')
    info = {'jobs': [unijob for unijob in
                    {x.job.id: {'name': x.job.funcname, 'state': x.job.state}
                     for x in dsjobs}.values()]}
    dbdsets = dm.Dataset.objects.filter(pk__in=dsids).select_related('quantdataset__quanttype')
    deleted = dbdsets.filter(deleted=True)
    if deleted.count():
        response['error'] = True
        response['errmsg'].append('Deleted datasets can not be analysed')
    dsetinfo = hv.populate_dset(dbdsets, request.user, showjobs=False, include_db_entry=True)
    qsfiles = {qsf.rawfile_id: qsf.projsample.sample for qsf in dm.QuantSampleFile.objects.filter(rawfile__dataset_id__in=dsids)}
    qfcsfiles = {qfcs.dsrawfile_id: qfcs.projsample.sample for qfcs in dm.QuantFileChannelSample.objects.filter(dsrawfile__dataset_id__in=dsids)}
    for dsid, dsdetails in dsetinfo.items():
        dset = dsdetails.pop('dbentry')
        if anid and am.AnalysisDatasetSetname.objects.filter(analysis_id=anid):
            adsn = dset.analysisdatasetsetname_set.get(analysis_id=anid)
            dsdetails['setname'] = adsn.setname.setname
            dsdetails['frregex'] = adsn.regex
        else:
            dsdetails['setname'] = ''
            dsdetails['frregex'] = '.*fr([0-9]+).*mzML$'
        dsdetails.update({'details': hv.fetch_dset_details(dset)})
        try:
            dsdetails['details']['qtype'] = dset.quantdataset.quanttype.name
            dsdetails['details']['qtypeshort'] = dset.quantdataset.quanttype.shortname
        except dm.QuantDataset.DoesNotExist:
            response['error'] = True
            response['errmsg'].append('Dataset with runname {} has no quant details, please fill in sample prep fields'.format(dsdetails['run']))
        else:
            nrneededfiles = dsdetails['details']['nrstoredfiles']['raw']
            dsfiles = get_dataset_files(dsid, use_refined=True)
    # FIXME default to refined mzmls if exist, now we enforce if exist for simplicity, make optional
    # FIXME if refined have been deleted, state it, maybe old auto-deleted and need to remake
            sample_error = False
            if dsfiles.count() != nrneededfiles:
                sample_error = True
                response['error'] = True
                response['errmsg'].append('Need to create or finish refining mzML files first in dataset {}'.format(dsdetails['run']))
            dsdetails['channels'] = {}
            dsdetails['files'] = {x.id: {'id': x.id, 'name': x.filename, 'fr': '', 'setname': ''} for x in dsfiles}
            qsf_error = False
            if 'lex' in dset.quantdataset.quanttype.name:
                for fn in dsfiles.select_related('rawfile__datasetrawfile__quantfilechannelsample__projsample'):
                    dsdetails['files'][fn.id]['sample'] = fn.rawfile.datasetrawfile.quantfilechannelsample.projsample.sample if hasattr(fn.rawfile.datasetrawfile, 'quantfilechannelsample') else ''
                dsdetails['details']['channels'] = {
                    ch.channel.channel.name: (ch.projsample.sample, ch.channel.channel_id) for ch in
                    dm.QuantChannelSample.objects.select_related(
                        'projsample', 'channel__channel').filter(dataset_id=dsid)}

            else:
                for fn in dsfiles.select_related('rawfile__datasetrawfile__quantsamplefile__projsample'):
                    try:
                        qsf_sample = fn.rawfile.datasetrawfile.quantsamplefile.projsample.sample
                    except dm.QuantSampleFile.DoesNotExist:
                        qsf_error = True
                    else:
                        dsdetails['files'][fn.id]['sample'] = qsf_sample
                if qsf_error:
                    response['error'] = True
                    response['errmsg'].append('File(s) in the dataset do '
                        'not have a sample annotation, please edit the dataset first')

            # Add stored analysis file-setnames if any:
            if anid:
                for afs in am.AnalysisFileSample.objects.filter(analysis_id=anid):
                    dsdetails['files'][afs.sfile_id]['setname'] = afs.sample
                dsdetails['filesaresets'] = any((x['setname'] != '' for x in dsdetails['files'].values()))
            elif not qsf_error and not sample_error:
                [x.update({'setname': x['sample'] if x['setname'] == '' else x['setname']})
                        for x in dsdetails['files'].values()]
                dsdetails['filesaresets'] = False
            # to list, keep ordering correct:
            dsdetails['files'] = [dsdetails['files'][x.id] for x in dsfiles]
    # FIXME labelfree quantsamplefile without sample prep error msg
    response['dsets'] = dsetinfo
    return JsonResponse(response)


@login_required
@require_GET
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
            'components': {psc.component.name: psc.component.value for psc in 
                wf.paramset.psetcomponent_set.all()},
            'flags': [{'nf': f.param.nfparam, 'id': f.param.pk, 'name': f.param.name,
                'help': f.param.help or False}
                for f in params.filter(param__ptype='flag', param__visible=True)],
            'numparams': [{'nf': p.param.nfparam, 'id': p.param.pk, 'name': p.param.name,
                'help': p.param.help or False} for p in params.filter(param__ptype='number')],
            'textparams': [{'nf': p.param.nfparam, 'id': p.param.pk, 'name': p.param.name,
                'help': p.param.help or False} for p in params.filter(param__ptype='text')],
            'multicheck': [{'nf': p.param.nfparam, 'id': p.param.pk, 'name': p.param.name,
                'opts': {po.pk: po.name for po in p.param.paramoption_set.all()},
                'help': p.param.help or False}
                for p in params.filter(param__ptype='multi', param__visible=True)],
            'fileparams': [{'name': f.param.name, 'id': f.param.pk, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 'allow_resultfile': f.allow_resultfiles,
                'help': f.param.help or False} for f in files],
            'multifileparams': [{'name': f.param.name, 'id': f.param.pk, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 'allow_resultfile': f.allow_resultfiles,
                'help': f.param.help or False} for f in multifiles],
            'fixedfileparams': [{'name': f.param.name, 'id': f.param.pk, 'nf': f.param.nfparam,
                'fn': f.libfile.sfile.filename,
                'sfid': f.libfile.sfile.id,
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
    qset_analysis = am.Analysis.objects.filter(datasetsearch__dataset__in=dsids,
            deleted=False).exclude(pk__in=superset_analysis)
    for dsid in dsids:
        qset_analysis = qset_analysis.filter(datasetsearch__dataset_id=dsid)
    resp['prev_resultfiles'] = [{'id': x.sfile.id, #'name': x.sfile.filename, 
        'name': '{} - Result of {} ({})'.format(x.sfile.filename, aj.get_ana_fullname(x.analysis), datetime.strftime(x.analysis.date, '%Y-%m-%d')),
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
    return HttpResponse('\n'.join(nfs.analysis.log), content_type="text/plain")


@login_required
@require_POST
def store_analysis(request):
    """Edits or stores a new analysis"""
    req = json.loads(request.body.decode('utf-8'))
    dsetquery = dm.Dataset.objects.filter(pk__in=req['dsids']).select_related('prefractionationdataset__prefractionation')
    if dsetquery.filter(deleted=True).exists():
        return JsonResponse({'error': 'Deleted datasets cannot be analyzed'})
    if req['analysis_id']:
        analysis = am.Analysis.objects.get(pk=req['analysis_id'])
        if analysis.user_id != request.user.id and not request.user.is_staff:
            return JsonResponse({'error': 'You do not have permission to edit this analysis'})
        elif analysis.nextflowsearch.job.state not in [jj.Jobstates.WAITING, jj.Jobstates.CANCELED, jj.Jobstates.ERROR]:
            return JsonResponse({'error': 'This analysis has a running or queued job, it cannot be edited, please stop the job first'})
        analysis.name = req['analysisname']
        analysis.save()
        dss = am.DatasetSearch.objects.filter(analysis=analysis)
        excess_dss = {x.dataset_id for x in dss}.difference(req['dsids'])
        dss.filter(dataset_id__in=excess_dss).delete()
        am.DatasetSearch.objects.bulk_create([am.DatasetSearch(dataset_id=dsid, analysis=analysis) 
            for dsid in set(req['dsids']).difference({x.dataset_id for x in dss})])
    else:
        analysis = am.Analysis(name=req['analysisname'], user_id=request.user.id)
        analysis.save()
        am.DatasetSearch.objects.bulk_create([am.DatasetSearch(dataset_id=dsid, analysis=analysis) for dsid in req['dsids']])

    components = {k: v for k, v in req['components'].items() if v}
    all_mzmldefs = am.WFInputComponent.objects.get(name='mzmldef').value
    jobinputs = {'components': {}, 'singlefiles': {}, 'multifiles': {}, 'params': {}}
    data_args = {'setnames': {}, 'platenames': {}}

    # Input files are passed as "fractions" currently, maybe make this cleaner in future
    data_args['fractions'] = req['fractions']

    # Mzml definition
    if 'mzmldef' in components:
        am.AnalysisMzmldef.objects.update_or_create(defaults={'mzmldef': components['mzmldef']}, analysis=analysis)
        jobinputs['components']['mzmldef'] = components['mzmldef']
    else:
        am.AnalysisMzmldef.objects.filter(analysis=analysis).delete()
        jobinputs['components']['mzmldef'] = False

    # Store setnames
    setname_ids = {}
    am.AnalysisSetname.objects.filter(analysis=analysis).exclude(setname__in=req['dssetnames'].values()).delete()
    for setname in set(req['dssetnames'].values()):
        anaset, created = am.AnalysisSetname.objects.get_or_create(analysis=analysis, setname=setname)
        setname_ids[setname] = anaset.pk
    # setnames for datasets, optionally fractions and strips
    new_ads = {}
    dsets = {str(dset.id): dset for dset in dsetquery}
    am.AnalysisDSInputFile.objects.filter(analysis=analysis).exclude(sfile_id__in=req['fractions']).delete()
    for dsid, setname in req['dssetnames'].items():
        if 'mzmldef' in components and 'plate' in all_mzmldefs[components['mzmldef']]:
            regex = req['frregex'][dsid] 
        else:
            regex = ''
        ads, created = am.AnalysisDatasetSetname.objects.update_or_create(
                defaults={'setname_id': setname_ids[setname], 'regex': regex},
                analysis=analysis, dataset_id=dsid) 
        new_ads[ads.pk] = created
        for sf in get_dataset_files(dsid, use_refined=True):
            am.AnalysisDSInputFile.objects.update_or_create(sfile=sf, analysis=analysis, analysisdset=ads)
            data_args['setnames'][sf.pk] = setname
        dset = dsets[dsid]
        if hasattr(dset, 'prefractionationdataset'):
            pfd = dset.prefractionationdataset
            if hasattr(pfd, 'hiriefdataset'):
                strip = '-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in str(pfd.hiriefdataset.hirief).split('-')])
                data_args['platenames'][dsid] = strip
            else:
                data_args['platenames'][dsid] = pfd.prefractionation.name
    am.AnalysisDatasetSetname.objects.filter(analysis=analysis).exclude(pk__in=new_ads).delete()

    # Check if files have not changed while editing an analysis (e.g. long open window)
    frontend_files_not_in_ds, ds_withfiles_not_in_frontend = {int(x) for x in req['fractions']}, set()
    for dsid in req['dsids']:
        for sf in get_dataset_files(dsid, use_refined=True):
            if sf.pk in frontend_files_not_in_ds:
                frontend_files_not_in_ds.remove(sf.pk)
            else:
                ds_withfiles_not_in_frontend.add(dsid)
    if len(frontend_files_not_in_ds) or len(ds_withfiles_not_in_frontend):
        return JsonResponse({'error': 'Files in dataset(s) have changed while you were editing. Please check the datasets marked.',
            'files_nods': list(frontend_files_not_in_ds), 'ds_newfiles': list(ds_withfiles_not_in_frontend)})

    # store samples if non-prefrac labelfree files are sets
    am.AnalysisFileSample.objects.filter(analysis=analysis).exclude(sfile_id__in=req['fnsetnames']).delete()
    for sfid, sample in req['fnsetnames'].items():
        am.AnalysisFileSample.objects.update_or_create(defaults={'sample': sample},
                analysis=analysis, sfile_id=sfid) 
    data_args['setnames'].update({sfid: sample for sfid, sample in req['fnsetnames'].items()})

    # Store params
    jobparams = defaultdict(list)
    passedparams_exdelete = {**req['params']['flags'], **req['params']['inputparams'], **req['params']['multicheck']}
    am.AnalysisParam.objects.filter(analysis=analysis).exclude(param_id__in=passedparams_exdelete).delete()
    paramopts = {po.pk: po.value for po in am.ParamOption.objects.all()}
    for pid, valueids in req['params']['multicheck'].items():
        ap, created = am.AnalysisParam.objects.update_or_create(param_id=pid, analysis=analysis,
                value=[int(x) for x in valueids])
        jobparams[ap.param.nfparam].extend([paramopts[x] for x in ap.value])
    for pid in req['params']['flags'].keys():
        ap, created = am.AnalysisParam.objects.update_or_create(analysis=analysis, param_id=pid, value=True)
        jobparams[ap.param.nfparam] = ['']
    for pid, value in req['params']['inputparams'].items():
        ap, created = am.AnalysisParam.objects.update_or_create(
            defaults={'value': value}, analysis=analysis, param_id=pid)
        jobparams[ap.param.nfparam].append(ap.value)

    # store parameter files
    # TODO remove single/multifiles distinction when no longer in use in home etc
    # Delete multifiles from old analysis and any old params that are not in request
    am.AnalysisFileParam.objects.filter(analysis=analysis).exclude(
            param_id__in=req['singlefiles']).delete()
    for pid, sfid in req['singlefiles'].items():
        afp, created = am.AnalysisFileParam.objects.update_or_create(defaults={'sfile_id': sfid}, analysis=analysis, param_id=pid)
        jobinputs['singlefiles'][afp.param.nfparam] = sfid
    # Re-create multifiles, they cannot be updated since all files map to analysis/param_id
    # resulting in only a single row in DB
    for pid, sfids in req['multifiles'].items():
        for sfid in sfids:
            afp = am.AnalysisFileParam.objects.create(sfile_id=sfid,
                    analysis=analysis, param_id=pid)
            try:
                jobinputs['multifiles'][afp.param.nfparam].append(sfid)
            except KeyError:
                jobinputs['multifiles'][afp.param.nfparam] = [sfid]

    # Labelcheck special stuff:
    is_lcheck = am.NextflowWfVersion.objects.filter(pk=req['nfwfvid'], paramset__psetcomponent__component__name='labelcheck').exists()
    if is_lcheck:
        try:
            qtype = dsetquery.values('quantdataset__quanttype__shortname').distinct().get()
        except dm.Dataset.MultipleObjectsReturned:
            return JsonResponse({'error': True, 'errmsg': 'Labelcheck pipeline cannot handle mixed isobaric types'})
        else:
            jobparams['--isobaric'] = [qtype['quantdataset__quanttype__shortname']]

    def parse_isoquant(quants):
        vals = {'sweep': False, 'report_intensity': False, 'denoms': {}}
        if quants['sweep']:
            vals['sweep'] = True
            calc_psm = 'sweep'
        elif quants['report_intensity']:
            vals['report_intensity'] = True
            calc_psm = 'intensity'
        elif quants['denoms']:
            vals['denoms'] = quants['denoms']
            calc_psm = ':'.join([ch for ch, is_denom in vals['denoms'].items() if is_denom])
        else:
            return False, False
        return vals, calc_psm

    isoq_cli = []
    # Base analysis
    if req['base_analysis']['selected']:
        # parse isoquants from base analysis (and possibly its base analysis,
        # which it will have accumulated)
        base_ana = am.Analysis.objects.select_related('analysissampletable').get(pk=req['base_analysis']['selected'])
        shadow_dss = {x.dataset_id: {'setname': x.setname.setname, 'regex': x.regex}
                for x in base_ana.analysisdatasetsetname_set.all()}
        if hasattr(base_ana, 'analysissampletable'):
            sampletables = base_ana.analysissampletable.samples
        else:
            sampletables = {}
        shadow_isoquants = get_isoquants(base_ana, sampletables)
        try:
            baseana_dbrec = am.AnalysisBaseanalysis.objects.get(analysis=base_ana)
        except am.AnalysisBaseanalysis.DoesNotExist:
            pass
        else:
            shadow_dss.update(baseana_dbrec.shadow_dssetnames)
            shadow_isoquants.update(baseana_dbrec.shadow_isoquants)
        # Remove current from previous (shadow) data if this is rerun 
        # and current isoquants are defined
        for setname in req['isoquant'].keys():
            if setname in shadow_isoquants:
                del(shadow_isoquants[setname])
        for dsid, setname in req['dssetnames'].items():
            if int(dsid) in shadow_dss:
                del(shadow_dss[int(dsid)])
            ads, created = am.AnalysisDatasetSetname.objects.update_or_create(
                    defaults={'setname_id': setname_ids[setname], 'regex': regex},
                    analysis=analysis, dataset_id=dsid) 
        base_def = {'base_analysis': base_ana,
                'is_complement': req['base_analysis']['isComplement'],
                'rerun_from_psms': req['base_analysis']['runFromPSM'],
                'shadow_isoquants': shadow_isoquants,
                'shadow_dssetnames': shadow_dss,
                }
        ana_base, cr = am.AnalysisBaseanalysis.objects.update_or_create(defaults=base_def, analysis_id=analysis.id)
        # Add base analysis isoquant to the job params if it is complement analysis
        if base_def['is_complement']:
            for setname, quants in shadow_isoquants.items():
                vals, calc_psm = parse_isoquant(quants)
                isoq_cli.append('{}:{}:{}'.format(setname, quants['chemistry'], calc_psm))
        # FIXME if fractionated, add the old mzmls for the plate QC count - yes that is necessary 
        # because plate names are not stored in the SQLite - maybe it should?
        # Options:
        # - store in SQL (msstitch change or dirty in the pipeline with an extra table - rather not?)
        # - pass old_mzmls to task in job, task with fn/instr/set/plate/fraction 
        # - store mzmldef in results, pass it automatically - easiest?
            
    # Add isobaric quant (NB there may already be some in the job params from base analysis above
    # FIXME isobaric quant is API v1/v2 diff, fix it
    # need passed: setname, any denom, or sweep or intensity
    if req['isoquant'] and not is_lcheck:
        am.AnalysisIsoquant.objects.filter(analysis=analysis).exclude(setname_id__in=setname_ids.values()).delete()
        for setname, quants in req['isoquant'].items():
            vals, calc_psm = parse_isoquant(quants)
            if not vals:
                return JsonResponse({'error': True, 'errmsg': 'Need to select one of sweep/intensity/denominator for set {}'.format(setname)})
            isoq_cli.append('{}:{}:{}'.format(setname, quants['chemistry'], calc_psm))
            am.AnalysisIsoquant.objects.update_or_create(defaults={'value': vals}, analysis=analysis, setname_id=setname_ids[setname])
        jobparams['--isobaric'] = [' '.join(isoq_cli)]

    # If any, store sampletable
    if 'sampletable' in components:
        sampletable = components['sampletable']
        am.AnalysisSampletable.objects.update_or_create(defaults={'samples': sampletable}, analysis=analysis)
        # check if we need to concat shadow isoquants to sampletable that gets passed to job
        if req['base_analysis']['isComplement']:
            for sname, isoq in shadow_isoquants.items():
                for ch, (sample, chid) in isoq['channels'].items():
                    sampletable.append([ch, sname, sample, isoq['samplegroups'][ch]])
        # strip empty last-fields (for no-group analysis)
        sampletable = [[f for f in row if f] for row in sampletable]
        jobinputs['components']['sampletable'] = sampletable
    else:
        jobinputs['components']['sampletable'] = False
        am.AnalysisSampletable.objects.filter(analysis=analysis).delete()

    # All data collected, now create a job in WAITING state
    fname = 'run_nf_search_workflow'
    jobinputs['params'] = [x for nf, vals in jobparams.items() for x in [nf, ';'.join([str(v) for v in vals])]]
    param_args = {'wfv_id': req['nfwfvid'], 'inputs': jobinputs}
    kwargs = {'analysis_id': analysis.id, 'wfv_id': req['nfwfvid'], 'inputs': jobinputs, **data_args}
    if req['analysis_id']:
        job = analysis.nextflowsearch.job
        job.kwargs = kwargs
        job.state = jj.Jobstates.WAITING
        job.save()
    else:
        job = jj.create_job(fname, state=jj.Jobstates.WAITING, **kwargs)
    am.NextflowSearch.objects.update_or_create(defaults={'nfworkflow_id': req['nfwfvid'], 'job_id': job.id, 'workflow_id': req['wfid'], 'token': ''}, analysis=analysis)
    return JsonResponse({'error': False, 'analysis_id': analysis.id})


def get_isoquants(analysis, sampletables):
    """For analysis passed, return its analysisisoquants from DB in nice format for frontend"""
    isoquants = {}
    for aiq in am.AnalysisIsoquant.objects.select_related('setname').filter(analysis=analysis):
        set_dsets = aiq.setname.analysisdatasetsetname_set.all()
        qtypename = set_dsets.values('dataset__quantdataset__quanttype__shortname').distinct().get()['dataset__quantdataset__quanttype__shortname']
        qcsamples = {qcs.channel.channel_id: qcs.projsample.sample for qcs in dm.QuantChannelSample.objects.filter(dataset_id__in=set_dsets.values('dataset'))}
        channels = {qtc.channel.name: qtc.channel_id for anasds in set_dsets.distinct('dataset__quantdataset__quanttype') for qtc in anasds.dataset.quantdataset.quanttype.quanttypechannel_set.all()}
        isoquants[aiq.setname.setname] = {
                'chemistry': qtypename,
                'channels': {name: (qcsamples[chid], chid) for name, chid in channels.items()},
                'samplegroups': {samch[0]: samch[3] for samch in sampletables if samch[1] == aiq.setname.setname},
                'denoms': aiq.value['denoms'],
                'report_intensity': aiq.value['report_intensity'],
                'sweep': aiq.value['sweep'],
                }
    return isoquants


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
    webshare = ServerShare.objects.get(name=settings.WEBSHARENAME)
    # Delete files on web share here since the job tasks run on storage cannot do that
    for webfile in rm.StoredFile.objects.filter(analysisresultfile__analysis__id=analysis.pk, servershare_id=webshare.pk):
        fpath = os.path.join(settings.WEBSHARE, webfile.path, webfile.filename)
        os.unlink(fpath)
    jj.create_job('purge_analysis', analysis_id=analysis.id)
    jj.create_job('delete_empty_directory',
            sf_ids=[x.sfile_id for x in analysis.analysisresultfile_set.all()])
    return JsonResponse({})


@login_required
def start_analysis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    try:
        if 'item_id' in req:
            # home app
            job = jm.Job.objects.get(nextflowsearch__id=req['item_id'])
        elif 'analysis_id' in req:
            # analysis start app
            job = jm.Job.objects.get(nextflowsearch__analysis_id=req['analysis_id'])
    except models.Job.DoesNotExist:
        return JsonResponse({'error': 'This job does not exist (anymore), it may have been deleted'}, status=403)
    ownership = jv.get_job_ownership(job, request)
    if not ownership['owner_loggedin'] and not ownership['is_staff']:
        return JsonResponse({'error': 'Only job owners and admin can start this job'}, status=403)
    elif job.state not in [jj.Jobstates.WAITING, jj.Jobstates.CANCELED]:
        return JsonResponse({'error': 'Only waiting/canceled jobs can be (re)started, this job is {}'.format(job.state)}, status=403)
    jv.do_retry_job(job)
    return JsonResponse({}) 


@login_required
def stop_analysis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    req = json.loads(request.body.decode('utf-8'))
    job = jm.Job.objects.get(nextflowsearch__id=req['item_id'])
    return jv.revoke_job(job.pk, request)


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


@require_POST
def upload_servable_file(request):
    data = request.POST
    if 'client_id' not in data or data['client_id'] !=settings.ANALYSISCLIENT_APIKEY:
        return JsonResponse({'msg': 'Forbidden'}, status=403)
    elif 'fname' not in data or data['fname'] not in settings.SERVABLE_FILENAMES:
        return JsonResponse({'msg': 'File is not servable'}, status=406)
    else:
        print('Ready to upload')
        return JsonResponse({'msg': 'File can be uploaded and served'}, status=200)


def get_servable_files(resultfiles):
    return resultfiles.filter(sfile__filename__in=settings.SERVABLE_FILENAMES)


def write_analysis_log(logline, analysis_id):
    entry = '[{}] - {}'.format(datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), logline)
    analysis = am.Analysis.objects.get(pk=analysis_id)
    analysis.log.append(entry)
    analysis.save()


def nextflow_analysis_log(request):
    req = json.loads(request.body.decode('utf-8'))
    print(req)
    if 'runName' not in req or not req['runName']:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    try:
        nfs = am.NextflowSearch.objects.get(token=req['runName'])
    except am.NextflowSearch.DoesNotExist:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    if nfs.job.state not in [jj.Jobstates.PROCESSING, jj.Jobstates.REVOKING]:
        return JsonResponse({'error': 'Analysis does not exist'}, status=403)
    if req['event'] in ['started', 'completed']:
        logmsg = 'Nextflow reports: workflow {}'.format(req['event'])
    elif req['event'] == 'process_completed':
        walltime = str(timedelta(seconds=req['trace']['realtime'] / 1000))
        logmsg = 'Process {} completed in {}'.format(req['trace']['name'], walltime)
    else:
        # Not logging anything
        return HttpResponse()
    write_analysis_log(logmsg, nfs.analysis_id)
    return HttpResponse()


def append_analysis_log(request):
    req = json.loads(request.body.decode('utf-8'))
    write_analysis_log(req['message'], req['analysis_id'])
    return HttpResponse()
