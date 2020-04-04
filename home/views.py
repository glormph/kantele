from datetime import timedelta, datetime
import json
from celery import states as tstates

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db.models import Q, Sum, Max
from collections import OrderedDict

from kantele import settings
from datasets import models as dsmodels
from analysis import models as anmodels
from analysis import views as av
from datasets import jobs as dsjobs
from datasets.views import check_ownership, get_dset_storestate
from rawstatus import models as filemodels
from jobs import jobs as jj
from jobs import views as jv
from jobs import models as jm


@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {'tab': request.GET['tab'] if 'tab' in request.GET else 'datasets',
               'dsids': request.GET['dsids'].split(',') if 'dsids' in request.GET else [],
               'anids': request.GET['anids'].split(',') if 'anids' in request.GET else [],
               'projids': request.GET['projids'].split(',') if 'projids' in request.GET else [],
               'jobids': request.GET['jobids'].split(',') if 'jobids' in request.GET else [],
               'username': request.user.username}
    return render(request, 'home/home.html', context)


@login_required
def find_projects(request):
    searchterms = [x for x in request.GET['q'].split(',') if x != '']
    dsquery = Q(runname__name__icontains=searchterms[0])
    dsquery |= Q(runname__experiment__name__icontains=searchterms[0])
    dsquery |= Q(runname__experiment__project__name__icontains=searchterms[0])
    query = Q(name__icontains=searchterms[0])
    for term in searchterms[1:]:
        dssubquery = Q(runname__name__icontains=term)
        dssubquery |= Q(runname__experiment__name__icontains=term)
        dssubquery |= Q(runname__experiment__project__name__icontains=term)
        subquery |= Q(name__icontains=term)
        query &= subquery
        dsquery &= dssubquery
    dbdsets = dsmodels.Dataset.objects.filter(dsquery).select_related('runname__experiment__project').values('runname__experiment__project').distinct()
    query |= Q(pk__in=dbdsets)
    dbprojects = dsmodels.Project.objects.filter(query )
    if request.GET.get('inactive') == 'false':
        dbprojects = dbprojects.filter(active=True)
    items, order = populate_proj(dbprojects, request.user)
    return JsonResponse({'items': items, 'order': order})


@login_required
def find_datasets(request):
    """Loop through comma-separated q-param in GET, do a lot of OR queries on
    datasets to find matches. String GET-derived q-params by AND."""
    searchterms = [x for x in request.GET['q'].split(',') if x != '']
    query = Q(runname__name__icontains=searchterms[0])
    query |= Q(runname__experiment__name__icontains=searchterms[0])
    query |= Q(runname__experiment__project__name__icontains=searchterms[0])
    query |= Q(datatype__name__icontains=searchterms[0])
    #query |= Q(user__username__icontains=searchterms[0])
    try:
        float(searchterms[0])
    except ValueError:
        pass
    else:
        query |= Q(prefractionationdataset__hiriefdataset__hirief__start=searchterms[0])
        query |= Q(prefractionationdataset__hiriefdataset__hirief__end=searchterms[0])
    for term in searchterms[1:]:
        subquery = Q(runname__name__icontains=term)
        subquery |= Q(runname__experiment__name__icontains=term)
        subquery |= Q(runname__experiment__project__name__icontains=term)
        subquery |= Q(datatype__name__icontains=term)
        #subquery |= Q(user__username__icontains=term)
        try:
            float(term)
        except ValueError:
            pass
        else:
            subquery |= Q(prefractionationdataset__hiriefdataset__hirief__start=term)
            subquery |= Q(prefractionationdataset__hiriefdataset__hirief__end=term)
        query &= subquery
    dbdsets = dsmodels.Dataset.objects.filter(query)
    if request.GET['deleted'] == 'false':
        dbdsets = dbdsets.filter(deleted=False)
    dsets = populate_dset(dbdsets, request.user)
    return JsonResponse({'items': dsets, 'order': list(dsets.keys())})


@login_required
def find_analysis(request):
    """Loop through comma-separated q-param in GET, do a lot of OR queries on
    analysis to find matches. String GET-derived q-params by AND."""
    searchterms = [x for x in request.GET['q'].split(',') if x != '']
    query = Q(analysis__name__icontains=searchterms[0])
    query |= Q(workflow__name__icontains=searchterms[0])
    query |= Q(analysis__user__username__icontains=searchterms[0])
    for term in searchterms[1:]:
        subquery = Q(analysis__name__icontains=term)
        subquery |= Q(workflow__name__icontains=term)
        subquery |= Q(analysis__user__username__icontains=term)
        query &= subquery
    dbanalyses = anmodels.NextflowSearch.objects.filter(query)
    if request.GET['deleted'] == 'false':
        dbanalyses = dbanalyses.filter(analysis__deleted=False)
    items, it_order = populate_analysis(dbanalyses.order_by('-analysis__date'), request.user)
    return JsonResponse({'items': items, 'order': it_order})


@login_required
def show_analyses(request):
    if 'ids' in request.GET:
        ids = request.GET['ids'].split(',')
        dbanalyses = anmodels.NextflowSearch.objects.filter(pk__in=ids)
    else:
        # last 6month analyses of a user plus current analyses PENDING/PROCESSING
        run_ana = anmodels.NextflowSearch.objects.select_related(
            'workflow', 'analysis').filter(
            job__state__in=jj.JOBSTATES_WAIT, analysis__deleted=False).exclude(
            analysis__user_id=request.user.id)
        user_ana = anmodels.NextflowSearch.objects.select_related(
            'workflow', 'analysis').filter(
            analysis__user_id=request.user.id, analysis__deleted=False,
            analysis__date__gt=datetime.today() - timedelta(183))
        dbanalyses = user_ana | run_ana
    items, it_order = populate_analysis(dbanalyses.order_by('-analysis__date'), request.user)
    return JsonResponse({'items': items, 'order': it_order})


@login_required
def show_projects(request):
    if 'ids' in request.GET:
        pids = request.GET['ids'].split(',')
        dbprojects = dsmodels.Project.objects.filter(pk__in=pids)
    elif request.GET.get('userproj') in ['true', 'True', True]:
        # all active projects
        dsos = dsmodels.DatasetOwner.objects.filter(user=request.user).select_related('dataset__runname__experiment')
        dbprojects = dsmodels.Project.objects.filter(pk__in={x.dataset.runname.experiment.project_id for x in dsos})
    else:
        # all active projects
        dbprojects = dsmodels.Project.objects.all()
    if request.GET.get('showinactive') not in ['true', 'True', True]:
        dbprojects = dbprojects.filter(active=True)
    items, order = populate_proj(dbprojects, request.user)
    return JsonResponse({'items': items, 'order': order})


@login_required
def show_datasets(request):
    if 'ids' in request.GET:
        dsids = request.GET['ids'].split(',')
        dbdsets = dsmodels.Dataset.objects.filter(pk__in=dsids)
    else:
        # last month datasets of a user
        dbdsets = dsmodels.Dataset.objects.filter(deleted=False, datasetowner__user_id=request.user.id,
                                                  date__gt=datetime.today() - timedelta(30))
    dsets = populate_dset(dbdsets, request.user)
    return JsonResponse({'items': dsets, 'order': list(dsets.keys())})


@login_required
def find_files(request):
    """Loop through comma-separated q-param in GET, do a lot of OR queries on
    datasets to find matches. String GET-derived q-params by AND."""
    searchterms = [x for x in request.GET['q'].split(',') if x != '']
    query = Q(filename__icontains=searchterms[0])
    query |= Q(rawfile__name__icontains=searchterms[0])
    query |= Q(rawfile__producer__name__icontains=searchterms[0])
    query |= Q(path__icontains=searchterms[0])
    for term in searchterms[1:]:
        subquery = Q(filename__icontains=term)
        subquery |= Q(rawfile__name__icontains=term)
        subquery |= Q(rawfile__producer__name__icontains=term)
        subquery |= Q(path__icontains=term)
        query &= subquery
    dbfns = filemodels.StoredFile.objects.filter(query)
    if request.GET['deleted'] == 'false':
        dbfns = dbfns.filter(deleted=False, purged=False)
    return populate_files(dbfns)


@login_required
def show_files(request):
    if 'ids' in request.GET:
        fnids = request.GET['ids'].split(',')
        dbfns = filemodels.StoredFile.objects.filter(pk__in=fnids)
    else:
        # last week files 
        # FIXME this is a very slow query
        dbfns = filemodels.StoredFile.objects.filter(regdate__gt=datetime.today() - timedelta(7), deleted=False)
    return populate_files(dbfns)


def populate_files(dbfns):
    popfiles = {}
    for fn in dbfns.select_related('rawfile__datasetrawfile__dataset', 'analysisresultfile__analysis', 'swestorebackedupfile', 'pdcbackedupfile', 'filetype'):
        it = {'id': fn.id,
              'name': fn.filename,
              'date': datetime.strftime(fn.regdate if fn.filetype_id != int(settings.RAW_SFGROUP_ID) else fn.rawfile.date, '%Y-%m-%d %H:%M'),
              'ftype': fn.filetype.name,
              'analyses': [],
              'dataset': [],
              'jobs': [],
              'job_ids': [],
              'deleted': fn.deleted,
              'purged': fn.purged,
             }
        # TODO make unified backup model?
        try:
            it['backup'] = fn.swestorebackedupfile.success
        except filemodels.SwestoreBackedupFile.DoesNotExist:
            try:
                it['backup'] = fn.pdcbackedupfile.success
            except filemodels.PDCBackedupFile.DoesNotExist:
                it['backup'] = False
        if not fn.rawfile.claimed:
            it['owner'] = fn.rawfile.producer.name
        elif hasattr(fn.rawfile, 'datasetrawfile'):
            it['owner'] = fn.rawfile.datasetrawfile.dataset.datasetowner_set.select_related('user').first().user.username
            dsrf = fn.rawfile.datasetrawfile
            it['dataset'] = dsrf.dataset_id
            fjobs = filemodels.FileJob.objects.select_related('job').filter(storedfile_id=fn.id)
            currentjobs = fjobs.exclude(job__state__in=jj.JOBSTATES_DONE)
            it['job_ids'] = [x.job_id for x in currentjobs]
            it['jobs'] = [x.job.state for x in currentjobs]
            if fn.filetype.filetype == 'mzml':
                anjobs = fjobs.filter(job__nextflowsearch__isnull=False)
            elif fn.filetype_id == int(settings.RAW_SFGROUP_ID):
                mzmls = fn.rawfile.storedfile_set.filter(filetype__filetype='mzml')
                anjobs = filemodels.FileJob.objects.filter(storedfile__in=mzmls, job__nextflowsearch__isnull=False)
            it['analyses'].extend([x.job.nextflowsearch.id for x in anjobs])
        elif hasattr(fn, 'analysisresultfile'):
            it['owner'] = fn.analysisresultfile.analysis.user.username
            if hasattr(fn.analysisresultfile.analysis, 'nextflowsearch'):
                it['analyses'].append(fn.analysisresultfile.analysis.nextflowsearch.id)
        popfiles[fn.id] = it
    order = [x['id'] for x in sorted(popfiles.values(), key=lambda x: x['date'], reverse=True)]
    return JsonResponse({'items': popfiles, 'order': order})


def get_ds_jobs(dbdsets):
    # FIXME probably do this in DB operation instead? its slow!
    jobmap = {}
    for filejob in filemodels.FileJob.objects.select_related('job').exclude(
            job__state__in=jj.JOBSTATES_DONE).filter(
            storedfile__rawfile__datasetrawfile__dataset_id__in=dbdsets):
        job = filejob.job
        try:
            jobmap[filejob.storedfile.rawfile.datasetrawfile.dataset_id][str(job.id)] = job.state
        except KeyError:
            jobmap[filejob.storedfile.rawfile.datasetrawfile.dataset_id] = {str(job.id): job.state}
    return jobmap


@login_required
def show_jobs(request):
    items = {}
    order = {'user': {x: [] for x in jj.JOBSTATES_WAIT + [jj.Jobstates.ERROR] + jj.JOBSTATES_DONE},
             'admin': {x: [] for x in jj.JOBSTATES_WAIT + [jj.Jobstates.ERROR] + jj.JOBSTATES_DONE}}
    if 'ids' in request.GET:
        jobids = request.GET['ids'].split(',')
        dbjobs = jm.Job.objects.filter(pk__in=jobids)
    else:
        dbjobs = jm.Job.objects.exclude(state__in=jj.JOBSTATES_DONE)
    for job in dbjobs.select_related('nextflowsearch__analysis__user').order_by('-timestamp'):
        ownership = jv.get_job_ownership(job, request)
        order[ownership['type']][job.state].append(job.id)
        analysis = jv.get_job_analysis(job)
        items[job.id] = {'id': job.id, 'name': job.funcname,
                         'state': job.state,
                         'canceled': job.state == jj.Jobstates.CANCELED,
                         'usr': ', '.join(ownership['usernames']),
                         'date': datetime.strftime(job.timestamp, '%Y-%m-%d'),
                         'analysis': analysis.nextflowsearch.id if analysis else False,
                         'actions': get_job_actions(job, ownership)}
        items[job.id]['fn_ids'] = [x.storedfile_id for x in job.filejob_set.all()]
        kwargs = json.loads(job.kwargs)
        dsets = kwargs.get('dset_id', kwargs.get('dset_ids', []))
        if type(dsets) == int:
            dsets = [dsets]
        items[job.id]['dset_ids'] = dsets
    stateorder = [jj.Jobstates.ERROR, jj.Jobstates.PROCESSING, jj.Jobstates.PENDING, jj.Jobstates.WAITING]
    #####/tasks
    #analysis = jv.get_job_analysis(job)
    #if analysis:
    #    analysis = analysis.name
    #errors = []
    #try:
    #    errormsg = job.joberror.message
    #except jm.JobError.DoesNotExist:
    #    errormsg = False
    #return JsonResponse({'files': fj.count(), 'dsets': 0, 
    #                     'analysis': analysis, 
    #                     'time': datetime.strftime(job.timestamp, '%Y-%m-%d %H:%M'),
    #                     'errmsg': errormsg,
    #                     'tasks': {'error': tasks.filter(state=tstates.FAILURE).count(),
    #                               'procpen': tasks.filter(state=tstates.PENDING).count(),
    #                               'done': tasks.filter(state=tstates.SUCCESS).count()},
    #                     'errors': errors,
    #                    })
#####

    return JsonResponse({'items': items, 'order': 
                         [x for u in ['user', 'admin'] for s in stateorder 
                          for x in order[u][s]]})


def get_job_actions(job, ownership):
    actions = []
    if job.state == jj.Jobstates.ERROR and (ownership['is_staff'] or ownership['owner_loggedin']) and jv.is_job_retryable_ready(job):
        actions.append('retry')
    elif job.state == jj.Jobstates.PROCESSING and ownership['is_staff']:
        actions.append('force retry')
    if ownership['is_staff'] and job.state not in jj.JOBSTATES_DONE:
        actions.append('delete')
    return actions


def populate_analysis(nfsearches, user):
    ana_out, order = {}, []
    nfsearches = nfsearches.select_related('analysis', 'job', 'workflow', 'nfworkflow')
    for nfs in nfsearches:
        fjobs = nfs.job.filejob_set.all().select_related(
            'storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project')
        fjobdsets = fjobs.distinct('storedfile__rawfile__datasetrawfile__dataset')
        try:
            ana_out[nfs.id] = {
                'id': nfs.id,
                'own': nfs.analysis.user_id == user.id,
                'usr': nfs.analysis.user.username,
                'name': nfs.analysis.name,
                'date': datetime.strftime(nfs.analysis.date, '%Y-%m-%d'),
                'jobstate': nfs.job.state,
                'jobid': nfs.job_id,
                'wf': nfs.workflow.name,
                'wflink': nfs.nfworkflow.nfworkflow.repo,
                'deleted': nfs.analysis.deleted,
                'purged': nfs.analysis.purged,
                'dset_ids': [x.storedfile.rawfile.datasetrawfile.dataset_id for x in fjobdsets],
                'fn_ids': [x.storedfile_id for x in fjobs],
            }
        except:
        # FIXME this dont work except anmodels.Analysis.RelatedObjectDoesNotExist:
            pass
        else:
            order.append(nfs.id)
    return ana_out, order


@login_required
def get_proj_info(request, proj_id):
    files = filemodels.StoredFile.objects.select_related('rawfile__producer', 'filetype').filter(
        rawfile__datasetrawfile__dataset__runname__experiment__project_id=proj_id)
    sfiles = {}
    for sfile in files:
        try:
            sfiles[sfile.filetype.name].append(sfile)
        except KeyError:
            sfiles[sfile.filetype.name] = [sfile]
    def getxbytes(bytes, op=50):
        if bytes is None:
            return '0B'
        if bytes >> op:
            return '{}{}B'.format(bytes >> op, {10:'K', 20:'M', 30:'G', 40:'T', 50:'P'}[op])
        else:
            return getxbytes(bytes, op-10)

    dsowners = dsmodels.DatasetOwner.objects.filter(dataset__runname__experiment__project_id=proj_id).distinct()
    info = {'owners': {x.user_id: x.user.username for x in dsowners},
            'stored_total_xbytes': getxbytes(files.aggregate(Sum('rawfile__size'))['rawfile__size__sum']),
            'stored_bytes': {ft: getxbytes(sum([fn.rawfile.size for fn in fns])) for ft, fns in sfiles.items()},
            'nrstoredfiles': {ft: len([fn for fn in fns]) for ft, fns in sfiles.items()},
            'instruments': list(set([x.rawfile.producer.name for x in files])),
            'nrbackupfiles': filemodels.SwestoreBackedupFile.objects.filter(
                storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project_id=proj_id).count() + filemodels.PDCBackedupFile.objects.filter(
                    storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project_id=proj_id).count(),
        }
    return JsonResponse(info)


def populate_proj(dbprojs, user, showjobs=True, include_db_entry=False):
    projs, order = {}, []
    dbprojs = dbprojs.annotate(Max('experiment__runname__dataset__date')).annotate(Max('experiment__runname__dataset__datasetsearch__analysis__date'))
    for proj in dbprojs.order_by('-experiment__runname__dataset__date__max'): # latest first

        order.append(proj.id)
        projs[proj.id] = {
            'id': proj.id,
            'name': proj.name,
            'inactive': proj.active == False,
            'start': proj.registered,
            'ptype': proj.projtype.ptype.name,
            'details': False,
            'selected': False,
        }
        # last active: last added dataset, last run analysis
        dsmax, anmax = proj.experiment__runname__dataset__date__max, proj.experiment__runname__dataset__datasetsearch__analysis__date__max
        if dsmax and anmax:
            projs[proj.id]['lastactive'] = sorted([dsmax, anmax])[-1]
        elif dsmax:

            projs[proj.id]['lastactive'] = dsmax
        elif anmax:
            projs[proj.id]['lastactive'] = anmax
        else:
            projs[proj.id]['lastactive'] = proj.registered
    return projs, order


def populate_dset(dbdsets, user, showjobs=True, include_db_entry=False):
    dsets = OrderedDict()
    for dataset in dbdsets.select_related('runname__experiment__project__projtype__ptype',
            'prefractionationdataset'):
        dsfiles = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset=dataset)
        storestate = get_dset_storestate(dataset, dsfiles)
        ana_ids = [x.id for x in anmodels.NextflowSearch.objects.filter(analysis__datasetsearch__dataset_id=dataset.id)]
        dsets[dataset.id] = {
            'id': dataset.id,
            'own': check_ownership(user, dataset),
            'usr': dataset.datasetowner_set.select_related('user').first().user.username,
            'deleted': dataset.deleted,
            'proj': dataset.runname.experiment.project.name,
            'ana_ids': ana_ids,
            'exp': dataset.runname.experiment.name,
            'run': dataset.runname.name,
            'dtype': dataset.datatype.name,
            'storestate': storestate,
            'fn_ids': [x.id for x in dsfiles],
            'ptype': dataset.runname.experiment.project.projtype.ptype.name,
        }
        if showjobs:
            jobmap = get_ds_jobs(dbdsets)
            dsets[dataset.id]['jobstates'] = list(jobmap[dataset.id].values()) if dataset.id in jobmap else []
            dsets[dataset.id]['jobids'] = ','.join(list(jobmap[dataset.id].keys())) if dataset.id in jobmap else []
        if hasattr(dataset, 'prefractionationdataset'):
            pf = dataset.prefractionationdataset
            dsets[dataset.id]['prefrac'] = str(pf.prefractionation.name)
            if 'hirief' in pf.prefractionation.name.lower():
                dsets[dataset.id]['hr'] = '{} {}'.format('HiRIEF', str(pf.hiriefdataset.hirief))
        if include_db_entry:
            dsets[dataset.id]['dbentry'] = dataset
    return dsets


# Ds page links to projects/files/analyses
# Project page links to files/analyses/datasets
# Etc CANNOT dynamically code the table too much
# Make three tables and make them share some code but not all

def get_analysis_invocation(job):
    kwargs = json.loads(job.kwargs)
    # TODO remove old jobs from system so we dont need to check this:
    if kwargs == {}:
        return {'params': [], 'files': []}
    params = kwargs['inputs']
    fnmap = {x['pk']: (x['filename'], x['libraryfile__description'], x['userfile__description']) for x in filemodels.StoredFile.objects.filter(pk__in=params['singlefiles'].values()).values('pk', 'filename', 'libraryfile__description', 'userfile__description')}
    for pk, fn in fnmap.items():
        # description is library file or userfile or nothing, pick
        if fn[1] is not None:
            desc = fn[1]
        elif fn[2] is not None:
            desc = fn[2]
        else:
            desc = ''
        fnmap[pk] = [fn[0], desc]
    invoc = {'files': [[x[0], *fnmap[x[1]]] for x in params['singlefiles'].items()]}
    invoc['params'] = params['params']
    if 'sampletable' in params:
        invoc['sampletable'] = [x for x in params['sampletable']]
    else:
        invoc['sampletable'] = False
    return invoc

    
@login_required
def get_analysis_info(request, nfs_id):
    nfs = anmodels.NextflowSearch.objects.filter(pk=nfs_id).select_related(
        'analysis', 'job', 'workflow', 'nfworkflow').get()
    #storeloc = {'{}_{}'.format(x.sfile.servershare.name, x.sfile.path): x.sfile for x in
    #            anmodels.AnalysisResultFile.objects.filter(analysis_id=nfs.analysis_id)}
    fjobs = nfs.job.filejob_set.all().select_related(
        'storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project')
    dsets =  {x.storedfile.rawfile.datasetrawfile.dataset for x in fjobs}
    #projs = {x.runname.experiment.project for x in dsets}
    if nfs.analysis.log == '':
        logentry = ['Analysis without logging or not yet queued']
    else:
        logentry = [x for y in json.loads(nfs.analysis.log) for x in y.split('\n') if x][-3:]
    linkedfiles = [(x.id, x.sfile.filename) for x in av.get_servable_files(nfs.analysis.analysisresultfile_set.select_related('sfile'))]
    resp = {#'jobs': {nfs.job.id: {'name': nfs.job.funcname, 'state': nfs.job.state,
            #                    'retry': jv.is_job_retryable_ready(nfs.job), 'id': nfs.job.id,
            #                    'time': nfs.job.timestamp}},
            'name': nfs.analysis.name,
            'wf': {'fn': nfs.nfworkflow.filename, 
                   'update': nfs.nfworkflow.update,
                   'repo': nfs.nfworkflow.nfworkflow.repo},
#             'proj': [{'name': x.name, 'id': x.id} for x in projs],
            'nrdsets': len(dsets),
            'nrfiles': fjobs.count(),
#             'storage_locs': [{'server': x.servershare.name, 'path': x.path}
#                              for x in storeloc.values()],
            'log': logentry, 
            'servedfiles': linkedfiles,
            'invocation': get_analysis_invocation(nfs.job),
            }
    # FIXME dsets, files are already counted in the non-detailed view, so maybe frontend can reuse those
    try:
        resp['quants'] = list({x.quantdataset.quanttype.name for x in dsets})
    except dsmodels.QuantDataset.DoesNotExist:
        resp['quants'] = []
    return JsonResponse(resp)


@login_required
def refresh_job(request, job_id):
    # FIXME share with show_jobs
    job = jm.Job.objects.get(pk=job_id)
    ownership = jv.get_job_ownership(job, request)
    return JsonResponse({'state': job.state,
                         'canceled': job.state == jj.Jobstates.CANCELED,
                         'actions': get_job_actions(job, ownership)})


@login_required
def get_job_info(request, job_id):
    job = jm.Job.objects.select_related('joberror').get(pk=job_id)
    tasks = job.task_set.all()
    fj = job.filejob_set
    analysis = jv.get_job_analysis(job)
    if analysis:
        analysis = analysis.name
    errors = []
    try:
        errormsg = job.joberror.message
    except jm.JobError.DoesNotExist:
        errormsg = False
    for task in tasks.filter(state=tstates.FAILURE, taskerror__isnull=False):
        # Tasks chained in a taskchain are all set to error when one errors, 
        # otherwise we cannot retry jobs since that waits for all tasks to finish.
        # This means we have to check for taskerror__isnull here
        errors.append({'msg': task.taskerror.message, 'args': task.args})
    return JsonResponse({'files': fj.count(), 'dsets': 0, 
                         'analysis': analysis, 
                         'time': datetime.strftime(job.timestamp, '%Y-%m-%d %H:%M'),
                         'errmsg': errormsg,
                         'tasks': {'error': tasks.filter(state=tstates.FAILURE).count(),
                                   'procpen': tasks.filter(state=tstates.PENDING).count(),
                                   'done': tasks.filter(state=tstates.SUCCESS).count()},
                         'errors': errors,
                        })


@login_required
def get_dset_info(request, dataset_id):
    dset = dsmodels.Dataset.objects.filter(pk=dataset_id).select_related(
        'runname__experiment__project').get()
    info = fetch_dset_details(dset)
    return JsonResponse(info)


@login_required
def get_file_info(request, file_id):
    sfile = filemodels.StoredFile.objects.filter(pk=file_id).select_related(
        'filetype', 'rawfile__datasetrawfile', 'analysisresultfile__analysis', 'libraryfile', 'userfile').get()
    info = {'server': sfile.servershare.name, 'path': sfile.path, 'analyses': [],
            'producer': sfile.rawfile.producer.name,
            'filename': sfile.filename,
            'renameable': True if sfile.filetype_id not in 
            [settings.MZML_SFGROUP_ID, settings.REFINEDMZML_SFGROUP_ID] else False}
    if hasattr(sfile, 'libraryfile'):
        desc = sfile.libraryfile.description
    elif hasattr(sfile, 'userfile'):
        desc = sfile.userfile.description
    else:
        desc = False
    info['description'] = desc
    if hasattr(sfile.rawfile, 'datasetrawfile'):
        dsrf = sfile.rawfile.datasetrawfile
        info['dataset'] = dsrf.dataset_id
        if sfile.filetype.filetype == 'mzml':
            anjobs = filemodels.FileJob.objects.filter(storedfile_id=file_id, job__nextflowsearch__isnull=False)
        elif sfile.filetype_id == int(settings.RAW_SFGROUP_ID):
            mzmls = sfile.rawfile.storedfile_set.filter(filetype__filetype='mzml')
            anjobs = filemodels.FileJob.objects.filter(storedfile__in=mzmls, job__nextflowsearch__isnull=False)
        info['analyses'].extend([x.job.nextflowsearch.id for x in anjobs])
    if hasattr(sfile, 'analysisresultfile') and hasattr(sfile.analysisresultfile.analysis, 'nextflowsearch'):
        info['analyses'].append(sfile.analysisresultfile.analysis.nextflowsearch.id)
    return JsonResponse(info)


def get_nr_raw_mzml_files(files, info):
    storedfiles = {'raw': files.filter(filetype_id__in=[settings.RAW_SFGROUP_ID, settings.BRUKER_SFGROUP_ID]).count(),
                   'mzML': files.filter(filetype_id=settings.MZML_SFGROUP_ID,
                       purged=False, checked=True).count(),
                   'refined_mzML': files.filter(filetype_id=settings.REFINEDMZML_SFGROUP_ID,
                       purged=False, checked=True).count()}
    info.update({'refinable': False, 'mzmlable': 'ready'})
    mzjobs = filemodels.FileJob.objects.exclude(job__state=jj.Jobstates.DONE).filter(
        storedfile__in=files, job__funcname__in=['refine_mzmls', 'convert_dataset_mzml']).distinct(
                'job').values('job__funcname')
    mzjobs = set([x['job__funcname'] for x in mzjobs])
    if storedfiles['raw'] == 0:
        info['mzmlable'] = False
        info['refinable'] = False
    elif storedfiles['mzML'] == storedfiles['raw']:
        info['mzmlable'] = False
        if 'refine_mzmls' in mzjobs:
            info['refinable'] = 'blocked'
        elif not storedfiles['refined_mzML']:
            info['refinable'] = 'ready'
        elif storedfiles['refined_mzML'] != storedfiles['raw']:
            info['refinable'] = 'partly'
    elif 'convert_dataset_mzml' in mzjobs:
        info['mzmlable'] = 'blocked'
    return storedfiles, info


def fetch_dset_details(dset):
    # FIXME add more datatypes and microscopy is hardcoded
    info = {'owners': {x.user_id: x.user.username for x in dset.datasetowner_set.select_related('user').all()},
            'allowners': {x.id: '{} {}'.format(x.first_name, x.last_name) for x in User.objects.filter(is_active=True)}, 
            'pwiz_versions': ['v3.0.19127'],
            'refine_versions': ['v1.0'],
            #[x.version for x in anmodels.Proteowizard.objects.all()]
            }
    try:
        info['qtype'] = {'name': dset.quantdataset.quanttype.name, 
                         'short': dset.quantdataset.quanttype.shortname}
    except dsmodels.QuantDataset.DoesNotExist:
        info['qtype'] = False
    nonms_dtypes = {x.id: x.name for x in dsmodels.Datatype.objects.all()
                    if x.name in ['microscopy']}
    files = filemodels.StoredFile.objects.select_related('rawfile__producer', 'servershare', 'filetype').filter(
        rawfile__datasetrawfile__dataset_id=dset.id)
    servers = [x[0] for x in files.distinct('servershare').values_list('servershare__uri')]
    info['storage_loc'] = '{} - {}'.format(';'.join(servers), dset.storage_loc)
    info['instruments'] = list(set([x.rawfile.producer.name for x in files]))
    info['instrument_types'] = list(set([x.rawfile.producer.shortname for x in files]))
    rawfiles = files.filter(filetype_id=settings.RAW_SFGROUP_ID)
    if dset.datatype_id not in nonms_dtypes:
        nrstoredfiles, info = get_nr_raw_mzml_files(files, info)
        mzmlfiles = files.filter(filetype_id=settings.MZML_SFGROUP_ID, purged=False, checked=True)
#        nrstoredfiles = {'raw': files.filter(filetype_id=settings.RAW_SFGROUP_ID).count(),
#                         'mzML': mzmlfiles.filter(mzmlfile__refined=False).count(),
#                         'refined_mzML': mzmlfiles.filter(mzmlfile__refined=True).count()}
    else:
        nrstoredfiles = {nonms_dtypes[dset.datatype_id]: rawfiles.count()}
    info['nrstoredfiles'] = nrstoredfiles
    info['nrbackupfiles'] = filemodels.PDCBackedupFile.objects.filter(
        storedfile__rawfile__datasetrawfile__dataset_id=dset.id).count()
    info['compstates'] = {x.dtcomp.component.name: x.state for x in
                          dsmodels.DatasetComponentState.objects.filter(
                              dataset_id=dset.id).select_related(
                                  'dtcomp__component')}
    return info


@login_required
def create_mzmls(request):
    if not request.method == 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    data = json.loads(request.body.decode('utf-8'))
    filters = ['"peakPicking true 2"', '"precursorRefine"']
    options = []
    if rawfile.producer.msinstrument.instrumenttype.name == 'timstof':
        filters.append('"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"')
        options.append('combineIonMobilitySpectra')
    if dsmodels.Dataset.objects.filter(pk=data['dsid'], deleted=False).count():
        jj.create_job('convert_dataset_mzml', options=options, filters=filters, dset_id=data['dsid'], pwiz_id=1)
    return JsonResponse({})


@login_required
def refine_mzmls(request):
    """Creates a job that runs the workflow with the latest version of the mzRefine containing NXF repo.
    Jobs and analysis entries are not created for dsets with full set of refined mzmls (403)."""
    if not request.method == 'POST':
        return JsonResponse({'error': 'Must use POST'}, status=405)
    data = json.loads(request.body.decode('utf-8'))
    # FIXME get analysis if it does exist, in case someone reruns?
    # Check if files lack refined mzMLs
    nr_refined = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=data['dsid'], filetype_id=settings.REFINEDMZML_SFGROUP_ID, checked=True).count()
    nr_mzml = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=data['dsid'], filetype_id=settings.MZML_SFGROUP_ID)
    if nr_mzml == nr_refined:
        return JsonResponse({'error': 'Refined data already exists'}, status=403)
    dset = dsmodels.Dataset.objects.select_related('quantdataset__quanttype').get(pk=data['dsid'])
    analysis = anmodels.Analysis(user_id=request.user.id, name='refine_dataset_{}'.format(data['dsid']))
    analysis.save()
    if dsmodels.Dataset.objects.filter(pk=data['dsid'], deleted=False).count():
        jj.create_job('refine_mzmls', dset_id=data['dsid'], analysis_id=analysis.id, wfv_id=settings.MZREFINER_NXFWFV_ID,
                dbfn_id=settings.MZREFINER_FADB_ID, qtype=dset.quantdataset.quanttype.shortname)
    return JsonResponse({})


@login_required
def show_messages(request):
    """Shows messages for admin and possibly also for normal users"""
    # Candidate messages for admin and normal:
    # purgable files
    # analysis is done
    # refine/convert is finished
    # if we are serious about this then we need to know if the message has been read yet...
    # Im not so interested in that, because then we need to generate the messages periodically or only 
    # on completion of jobs etc.
    # Maybe three types of message: 
    #  - dynamic (resolve it and it disappear)
    #  - notification from database (remove when read) - your job is done
    #  - expiring at date - check out our new functionality, maintenance coming
    max_age_old = 30 # days
    out = {'olddef': '{} days'.format(max_age_old)}
    if request.user.is_staff:
        purgable = anmodels.Analysis.objects.select_related('nextflowsearch', 'analysisdeleted').filter(deleted=True, purged=False)
        purgable_old = purgable.filter(analysisdeleted__date__lt=datetime.today() - timedelta(max_age_old))
        if purgable:
            purgable_ana = [x.nextflowsearch.id for x in purgable if hasattr(x, 'nextflowsearch')]
        else:
            purgable_ana = False
        if purgable_old:
            purgable_ana_old = [x.nextflowsearch.id for x in purgable_old if hasattr(x, 'nextflowsearch')]
        else:
            purgable_ana_old = False
        out['purgable_analyses'] = purgable_ana
        out['old_purgable_analyses'] = purgable_ana_old
        return JsonResponse(out)
    else:
        return JsonResponse({'error': 'User is not admin'}, status=403)
