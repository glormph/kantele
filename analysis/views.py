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
from jobs import views as jv
from jobs import models as jm


@login_required
def get_analysis_init(request):
    dsids = request.GET['dsids'].split(',')
    try:
        context = {'dsids': dsids, 'analysis': False}
    except:
        return HttpResponseForbidden()
    return render(request, 'analysis/analysis.html', context)


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
            'analysisname': re.sub('^[A-Z]+_', '', ana.name),
            'flags': [],
            'multicheck': [],
            'inputparams': {},
            'multifileparams': {},
            'fileparams': {},
            'isoquants': {},
            }
    for ap in ana.analysisparam_set.all():
        if ap.param.ptype == 'flag' and ap.value:
            analysis['flags'].append(ap.param.id)
        elif ap.param.ptype == 'multi':
            analysis['multicheck'].append('{}___{}'.format(ap.param.id, str(ap.value)))
        elif ap.param.ptype == 'number':
            analysis['inputparams'][ap.param_id] = ap.value
    pset = ana.nextflowsearch.nfworkflow.paramset
    multifiles = {x.param_id for x in pset.psetmultifileparam_set.all()}
    for afp in ana.analysisfileparam_set.all():
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
    for aiq in am.AnalysisIsoquant.objects.select_related('setname').filter(analysis=ana):
        set_dsets = aiq.setname.analysisdatasetsetname_set.all()
        qtypename = set_dsets.values('dataset__quantdataset__quanttype__shortname').get()['dataset__quantdataset__quanttype__shortname']
        qcsamples = {qcs.channel.channel_id: qcs.projsample.sample for qcs in dm.QuantChannelSample.objects.filter(dataset_id__in=set_dsets.values('dataset'))}
        channels = {qtc.channel.name: qtc.channel_id for anasds in set_dsets.distinct('dataset__quantdataset__quanttype') for qtc in anasds.dataset.quantdataset.quanttype.quanttypechannel_set.all()}
        analysis['isoquants'][aiq.setname.setname] = {
                'chemistry': qtypename,
                'channels': {name: (qcsamples[chid], chid) for name, chid in channels.items()},
                'samplegroups': {samch[0]: samch[3] if samch[3] != 'X__POOL' else '' for samch in sampletables if samch[1] == aiq.setname.setname},
                'denoms': aiq.value['denoms'],
                'report_intensity': aiq.value['intensity'],
                'sweep': aiq.value['sweep'],
                }
    context = {
            'dsids': [dss.dataset_id for dss in ana.datasetsearch_set.all()],
            'analysis': analysis
            }
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


def get_dataset_files(dsid, nrneededfiles):
    dsfiles = rm.StoredFile.objects.select_related('rawfile').filter(
        rawfile__datasetrawfile__dataset_id=dsid, checked=True, deleted=False, purged=False)
    refineddsfiles = dsfiles.filter(mzmlfile__refined=True)
    if refineddsfiles.count() and refineddsfiles.count() == nrneededfiles:
        dsfiles = refineddsfiles
    else:
        # TODO this gets only mzml files from the dataset:
        # If were going to pick other files by type we need to store that also in DB
        dsfiles = dsfiles.filter(mzmlfile__refined=False)
    return dsfiles


@login_required
def match_fractions(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    req = json.loads(request.body.decode('utf-8'))
    dsfiles = [{'name': fn.filename} for fn in get_dataset_files(req['dsid'], nrneededfiles=-1)]
    for fn in dsfiles:
        try:
            frnum = re.search(req['regex'], fn['name']).group(1)
        except IndexError:
            return JsonResponse({'error': True, 'errmsg': 'Need to define a regex group with parentheses around the fraction numbers'})
        else:
            fn['fr'] = frnum
    return JsonResponse({'error': False, 'fractions': dsfiles})


@login_required
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
    # FIXME default to refined mzmls if exist, now we enforce if exist for simplicity, make optional
    # FIXME if refined have been deleted, state it, maybe old auto-deleted and need to remake
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
            dsfiles = get_dataset_files(dsid, nrneededfiles)
            if dsfiles.count() != nrneededfiles:
                response['error'] = True
                response['errmsg'].append('Need to create or finish refining mzML files first in dataset {}'.format(dsdetails['run']))
            if 'lex' in dset.quantdataset.quanttype.name:
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'fr': '',
                    'sample': x.rawfile.datasetrawfile.quantfilechannelsample.projsample.sample if hasattr(x.rawfile.datasetrawfile, 'quantfilechannelsample') else '',
                    'setname': qfcsfiles[x.rawfile.datasetrawfile.id] if anid and x.rawfile.datasetrawfile.id in qfcsfiles else '',
                    } for x in dsfiles.select_related('rawfile__datasetrawfile__quantfilechannelsample__projsample')]
                dsdetails['details']['channels'] = {
                    ch.channel.channel.name: (ch.projsample.sample, ch.channel.channel_id) for ch in
                    dm.QuantChannelSample.objects.select_related(
                        'projsample', 'channel__channel').filter(dataset_id=dsid)}
            else:
                dsdetails['details']['channels'] = {}
                dsdetails['files'] = [{'id': x.id, 'name': x.filename, 'fr': '',
                    'sample': x.rawfile.datasetrawfile.quantsamplefile.projsample.sample,
                    'setname': qsfiles[x.rawfile.datasetrawfile.id] if anid else ''
                    } for x in dsfiles.select_related('rawfile__datasetrawfile__quantsamplefile__projsample')]
            if not anid:
                [x.update({'setname': x['sample'] if x['setname'] == '' else x['setname']}) for x in dsdetails['files']]
                dsdetails['filesaresets'] = False
            else:
                dsdetails['filesaresets'] = all((x['setname'] != '' for x in dsdetails['files']))
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
            'components': {psc.component.name: json.loads(psc.component.value) for psc in 
                wf.paramset.psetcomponent_set.all()},
            'flags': [{'nf': f.param.nfparam, 'id': f.param.pk, 'name': f.param.name} 
                for f in params.filter(param__ptype='flag', param__visible=True)],
            'numparams': [{'nf': p.param.nfparam, 'id': p.param.pk, 'name': p.param.name}
                for p in params.filter(param__ptype='number')],
            'multicheck': [{'nf': p.param.nfparam, 'id': p.param.pk, 'name': p.param.name,
                'opts': {po.pk: po.name for po in p.param.paramoption_set.all()}}
                for p in params.filter(param__ptype='multi', param__visible=True)],
            'fileparams': [{'name': f.param.name, 'id': f.param.pk, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 
                'allow_resultfile': f.allow_resultfiles} for f in files],
            'multifileparams': [{'name': f.param.name, 'id': f.param.pk, 'nf': f.param.nfparam,
                'ftype': f.param.filetype_id, 
                'allow_resultfile': f.allow_resultfiles} for f in multifiles],
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
def store_analysis(request):
    """Edits or stores a new analysis"""
    if request.method != 'POST':
        return HttpResponseNotAllowed(permitted_methods=['POST'])
    req = json.loads(request.body.decode('utf-8'))
    dsetquery = dm.Dataset.objects.filter(pk__in=req['dsids'])
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
    all_mzmldefs = json.loads(am.WFInputComponent.objects.get(name='mzmldef').value)
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
    for dsid, setname in req['dssetnames'].items():
        regex = ''
        ads, created = am.AnalysisDatasetSetname.objects.update_or_create(
                defaults={'setname_id': setname_ids[setname], 'regex': regex},
                analysis=analysis, dataset_id=dsid) 
        new_ads[ads.pk] = created
        data_args['setnames'].update({sf.pk: setname for sf in get_dataset_files(dsid, nrneededfiles=False)})
        if 'mzmldef' in components and 'plate' in all_mzmldefs[components['mzmldef']]:
            regex = req['frregex'][dsid] 
        dset = dsets[dsid]
        if hasattr(dset, 'prefractionationdataset'):
            pfd = dset.prefractionationdataset
            if hasattr(pfd, 'hiriefdataset'):
                strip = '-'.join([re.sub('.0$', '', str(float(x.strip()))) for x in str(pfd.hiriefdataset.hirief).split('-')])
                data_args['platenames'][dsid] = strip
    am.AnalysisDatasetSetname.objects.filter(analysis=analysis).exclude(pk__in=new_ads).delete()

    # store samples if non-prefrac labelfree files are sets
    am.AnalysisFileSample.objects.filter(analysis=analysis).exclude(sfile_id__in=req['fnsetnames']).delete()
    for sfid, sample in req['fnsetnames'].items():
        am.AnalysisFileSample.objects.update_or_create(defaults={'sample': sample},
                analysis=analysis, sfile_id=sfid) 
    data_args['setnames'].update({sfid: sample for sfid, sample in req['fnsetnames'].items()})

    # Store params
    jobparams = {}
    passedparams_exdelete = {**req['params']['flags'], **req['params']['inputparams']}
    am.AnalysisParam.objects.filter(analysis=analysis).exclude(param_id__in=passedparams_exdelete).delete()
    paramopts = {po.pk: po.value for po in am.ParamOption.objects.all()}
    am.AnalysisParam.objects.filter(analysis=analysis).delete()
    for pid, valueids in req['params']['multicheck'].items():
        for valueid in valueids:
            ap = am.AnalysisParam.objects.create(param_id=pid, value=int(valueid), analysis=analysis)
            try:
                jobparams[ap.param.nfparam].append(paramopts[ap.value])
            except KeyError:
                jobparams[ap.param.nfparam] = [paramopts[ap.value]]
    for pid in req['params']['flags'].keys():
        ap, created = am.AnalysisParam.objects.get_or_create(analysis=analysis, param_id=pid, value=True)
        jobparams[ap.param.nfparam] = ['']
    for pid, value in req['params']['inputparams'].items():
        ap, created = am.AnalysisParam.objects.update_or_create(
            defaults={'value': value}, analysis=analysis, param_id=pid)
        jobparams[ap.param.nfparam] = [ap.value]

    # store parameter files
    # TODO remove single/multifiles distinction when no longer in use in home etc
    am.AnalysisFileParam.objects.filter(analysis=analysis).exclude(
            param_id__in={**req['singlefiles'], **req['multifiles']}).delete()
    for pid, sfid in req['singlefiles'].items():
        afp, created = am.AnalysisFileParam.objects.update_or_create(defaults={'sfile_id': sfid}, analysis=analysis, param_id=pid)
        jobinputs['singlefiles'][afp.param.nfparam] = sfid
    for pid, sfids in req['multifiles'].items():
        for sfid in sfids:
            afp, created = am.AnalysisFileParam.objects.update_or_create(
                    defaults={'sfile_id': sfid}, analysis=analysis, param_id=pid)
            try:
                jobinputs['multifiles'][afp.param.nfparam].append(sfid)
            except KeyError:
                jobinputs['multifiles'][afp.param.nfparam] = [sfid]

    # If any, store sampletable
    if 'sampletable' in components:
        am.AnalysisSampletable.objects.update_or_create(defaults={'samples': components['sampletable']}, analysis=analysis)
        jobinputs['components']['sampletable'] = components['sampletable']
    else:
        jobinputs['components']['sampletable'] = False
        am.AnalysisSampletable.objects.filter(analysis=analysis).delete()

    # Labelcheck special stuff:
    is_lcheck = am.NextflowWfVersion.objects.filter(pk=req['nfwfvid'], paramset__psetcomponent__component__name='labelcheck').exists()
    if is_lcheck:
        try:
            qtype = dsetquery.values('quantdataset__quanttype__shortname').distinct().get()
        except dm.Dataset.MultipleObjectsReturned:
            return JsonResponse({'error': True, 'errmsg': 'Labelcheck pipeline cannot handle mixed isobaric types'})
        else:
            jobparams['--isobaric'] = qtype['quantdataset__quanttype__shortname']
            
    # FIXME isobaric quant is API v1/v2 diff, fix it
    # need passed: setname, any denom, or sweep or intensity
    if req['isoquant'] and not is_lcheck:
        am.AnalysisIsoquant.objects.filter(analysis=analysis).exclude(setname_id__in=setname_ids.values()).delete()
        isoq_cli = []
        for setname, quants in req['isoquant'].items():
            vals = {'sweep': False, 'intensity': False, 'denoms': []}
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
                return JsonResponse({'error': True, 'errmsg': 'Need to select one of sweep/intensity/denominator for set {}'.format(setname)})
            isoq_cli.append('{}:{}:{}'.format(setname, quants['chemistry'], calc_psm))
            am.AnalysisIsoquant.objects.update_or_create(defaults={'value': vals}, analysis=analysis, setname_id=setname_ids[setname])
        jobparams['--isobaric'] = [' '.join(isoq_cli)]

    # All data collected, now create a job in WAITING state
    fname = 'run_nf_search_workflow'
    jobinputs['params'] = [x for nf, vals in jobparams.items() for x in [nf, ';'.join([str(v) for v in vals])]]
    param_args = {'wfv_id': req['nfwfvid'], 'inputs': jobinputs}
    kwargs = {'analysis_id': analysis.id, 'wfv_id': req['nfwfvid'], 'inputs': jobinputs, **data_args}
    if req['analysis_id']:
        job = analysis.nextflowsearch.job
        job.kwargs = json.dumps(kwargs)
        job.state = jj.Jobstates.WAITING
        job.save()
    else:
        job = jj.create_job(fname, state=jj.Jobstates.WAITING, **kwargs)
        am.NextflowSearch.objects.update_or_create(defaults={'nfworkflow_id': req['nfwfvid'], 'job_id': job.id, 'workflow_id': req['wfid']}, analysis=analysis)
    return JsonResponse({'error': False, 'analysis_id': analysis.id})


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
        return JsonResponse({'error': 'Only waiting/canceled jobs can be (re)started'}, status=403)
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
