from datetime import timedelta, datetime
import json
from celery import states as tstates

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db.models import Q
from collections import OrderedDict

from kantele import settings
from datasets import models as dsmodels
from analysis import models as anmodels
from analysis import views as av
from datasets import jobs as dsjobs
from datasets.views import check_ownership
from rawstatus import models as filemodels
from jobs import jobs as jj
from jobs import models as jm


@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {'tab': request.GET['tab'] if 'tab' in request.GET else 'datasets',
               'dsids': request.GET['dsids'].split(',') if 'dsids' in request.GET else [],
               'anids': request.GET['anids'].split(',') if 'anids' in request.GET else [],
               'jobids': request.GET['jobids'].split(',') if 'jobids' in request.GET else [],
               'username': request.user.username}
    return render(request, 'home/home.html', context)


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
    return JsonResponse({'dsets': populate_dset(dbdsets, request.user)})


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
def show_datasets(request):
    if 'dsids' in request.GET:
        dsids = request.GET['dsids'].split(',')
        dbdsets = dsmodels.Dataset.objects.filter(pk__in=dsids)
    else:
        # last month datasets of a user
        dbdsets = dsmodels.Dataset.objects.filter(deleted=False, datasetowner__user_id=request.user.id,
                                                  date__gt=datetime.today() - timedelta(30))
    return JsonResponse({'dsets': populate_dset(dbdsets, request.user),
                         'allowners': {x.id: '{} {}'.format(x.first_name, x.last_name) for x in User.objects.filter(is_active=True)}})


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
    if 'fnids' in request.GET:
        fnids = request.GET['fnids'].split(',')
        dbfns = filemodels.StoredFile.objects.filter(pk__in=fnids)
    else:
        # last week files 
        # FIXME this is a very slow query
        dbfns = filemodels.StoredFile.objects.filter(regdate__gt=datetime.today() - timedelta(7), deleted=False)
    return populate_files(dbfns)


def populate_files(dbfns):
    popfiles = {}
    for fn in dbfns.select_related('rawfile__datasetrawfile__dataset', 'analysisresultfile__analysis', 'swestorebackedupfile', 'filetype'):
        it = {'id': fn.id,
              'name': fn.filename,
              'date': fn.regdate if fn.filetype_id != int(settings.RAW_SFGROUP_ID) else fn.rawfile.date,
              'stored': fn.servershare.name if fn.checked else False,
              'ftype': fn.filetype.name,
              'details': False,
             }
        try:
            it['backup'] = fn.swestorebackedupfile is not 0
        except filemodels.SwestoreBackedupFile.DoesNotExist:
            it['backup'] = False
        if not fn.rawfile.claimed:
            it['owner'] = fn.rawfile.producer.name
        elif hasattr(fn.rawfile, 'datasetrawfile'):
            it['owner'] = fn.rawfile.datasetrawfile.dataset.datasetowner_set.select_related('user').first().user.username
        elif hasattr(fn, 'analysisresultfile'):
            it['owner'] = fn.analysisresultfile.analysis.user.username
        popfiles[fn.id] = it
    order = [x['id'] for x in sorted(popfiles.values(), key=lambda x: x['date'], reverse=True)]
    return JsonResponse({'files': popfiles, 'order': order})


def get_ds_jobs(dbdsets):
    jobmap = {}
    for filejob in filemodels.FileJob.objects.select_related('job').exclude(
            job__state=jj.Jobstates.DONE).filter(
            storedfile__rawfile__datasetrawfile__dataset_id__in=dbdsets):
        job = filejob.job
        try:
            jobmap[filejob.storedfile.rawfile.datasetrawfile.dataset_id].add(job.state)
        except KeyError:
            jobmap[filejob.storedfile.rawfile.datasetrawfile.dataset_id] = {job.state}
    return jobmap


@login_required
def show_jobs(request):
    items = {}
    order = {'user': {x: [] for x in jj.JOBSTATES_WAIT + [jj.Jobstates.ERROR]},
             'admin': {x: [] for x in jj.JOBSTATES_WAIT + [jj.Jobstates.ERROR]}}
    for job in jm.Job.objects.exclude(state__in=jj.JOBSTATES_DONE).select_related(
            'nextflowsearch__analysis__user').order_by('-timestamp'):
        ownership = jj.get_job_ownership(job, request)
        order[ownership['type']][job.state].append(job.id)
        items[job.id] = {'id': job.id, 'name': job.funcname,
                         'state': job.state,
                         'details': False,
                         'usr': ', '.join(ownership['usernames']),
                         'date': datetime.strftime(job.timestamp, '%Y-%m-%d'),
                         'actions': get_job_actions(job, ownership)}
    stateorder = [jj.Jobstates.ERROR, jj.Jobstates.PROCESSING, jj.Jobstates.PENDING, jj.Jobstates.WAITING]
    return JsonResponse({'items': items, 'order': 
                         [x for u in ['user', 'admin'] for s in stateorder 
                          for x in order[u][s]]})


def get_job_actions(job, ownership):
    actions = []
    if job.state == jj.Jobstates.ERROR and (ownership['is_staff'] or ownership['owner_loggedin']) and jj.is_job_retryable_ready(job):
        actions.append('retry')
    elif job.state == jj.Jobstates.PROCESSING and ownership['is_staff']:
        actions.append('force retry')
    if ownership['is_staff'] and job.state not in jj.JOBSTATES_DONE:
        actions.append('delete')
    return actions


def populate_analysis(nfsearches, user):
    ana_out, order = {}, []
    for nfs in nfsearches:
        try:
            ana_out[nfs.id] = {
                'id': nfs.id,
                'own': nfs.analysis.user_id == user.id,
                'usr': nfs.analysis.user.username,
                'name': nfs.analysis.name,
                'date': datetime.strftime(nfs.analysis.date, '%Y-%m-%d'),
                'jobstates': [nfs.job.state],
                'wf': nfs.workflow.name,
                'deleted': nfs.analysis.deleted,
                'purged': nfs.analysis.purged,
                'details': False,
                'selected': False,
            }
        except:
        # FIXME this dont work except anmodels.Analysis.RelatedObjectDoesNotExist:
            pass
        else:
            order.append(nfs.id)
    return ana_out, order


def populate_dset(dbdsets, user, showjobs=True, include_db_entry=False):
    if showjobs:
        jobmap = get_ds_jobs(dbdsets)
    dsets = OrderedDict()
    for dataset in dbdsets.select_related('runname__experiment__project__projtype__ptype',
                                          'prefractionationdataset'):
        dsets[dataset.id] = {
            'id': dataset.id,
            'own': check_ownership(user, dataset),
            'usr': dataset.datasetowner_set.select_related('user').first().user.username,
            'deleted': dataset.deleted,
            'proj': dataset.runname.experiment.project.name,
            'exp': dataset.runname.experiment.name,
            'run': dataset.runname.name,
            'dtype': dataset.datatype.name,
            'ptype': dataset.runname.experiment.project.projtype.ptype.name,
            'details': False,
            'selected': False,
        }
        if showjobs:
            dsets[dataset.id]['jobstates'] = list(jobmap[dataset.id]) if dataset.id in jobmap else []
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
    params = json.loads(job.args)[7]
    if type(params) == int:
        return {'params': [], 'files': []}
    fnmap = {x['pk']: (x['filename'], x['libraryfile__description'], x['userfile__description']) for x in filemodels.StoredFile.objects.filter(pk__in=params['singlefiles'].values()).values('pk', 'filename', 'libraryfile__description', 'userfile__description')}
    for pk, fn in fnmap.items():
        if fn[1] is not None:
            desc = fn[1]
        elif fn[2] is not None:
            desc = fn[2]
        else:
            desc = ''
        fnmap[pk] = [fn[0], desc]
    invoc = {'files': [[x[0], *fnmap[x[1]]] for x in params['singlefiles'].items()]}
    invoc['params'] = params['params']
    return invoc

    
@login_required
def get_analysis_info(request, nfs_id):
    nfs = anmodels.NextflowSearch.objects.filter(pk=nfs_id).select_related(
        'analysis', 'job', 'workflow', 'nfworkflow').get()
    storeloc = {'{}_{}'.format(x.sfile.servershare.name, x.sfile.path): x.sfile for x in
                anmodels.AnalysisResultFile.objects.filter(analysis_id=nfs.analysis_id)}
    fjobs = nfs.job.filejob_set.all().select_related(
        'storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project')
    dsets =  {x.storedfile.rawfile.datasetrawfile.dataset for x in fjobs}
    projs = {x.runname.experiment.project for x in dsets}
    if nfs.analysis.log == '':
        logentry = ['Analysis without logging or not yet queued']
    else:
        logentry = [x for y in json.loads(nfs.analysis.log) for x in y.split('\n')][-10:]
    linkedfiles = [[x.sfile.filename, x.id] for x in 
                   av.get_servable_files(nfs.analysis.analysisresultfile_set.select_related('sfile'))]
    resp = {'jobs': {nfs.job.id: {'name': nfs.job.funcname, 'state': nfs.job.state,
                                'retry': jj.is_job_retryable_ready(nfs.job), 'id': nfs.job.id,
                                'time': nfs.job.timestamp}},
             'wf': {'fn': nfs.nfworkflow.filename, 
                    'commit': nfs.nfworkflow.commit,
                    'repo': nfs.nfworkflow.nfworkflow.repo},
             'proj': [{'name': x.name, 'id': x.id} for x in projs],
             'dsets': [x.id for x in dsets],
             'nrfiles': fjobs.count(),
             'storage_locs': [{'server': x.servershare.name, 'path': x.path}
                              for x in storeloc.values()],
             'log': logentry, 'servedfiles': linkedfiles,
             'invocation': get_analysis_invocation(nfs.job),
            }
    try:
        resp['quants'] = list({x.quantdataset.quanttype.name for x in dsets})
    except dsmodels.QuantDataset.DoesNotExist:
        pass
    return JsonResponse(resp)


@login_required
def refresh_job(request, job_id):
    job = jm.Job.objects.get(pk=job_id)
    ownership = jj.get_job_ownership(job, request)
    return JsonResponse({'state': job.state,
                         'actions': get_job_actions(job, ownership)})


@login_required
def get_job_info(request, job_id):
    job = jm.Job.objects.select_related('joberror').get(pk=job_id)
    tasks = job.task_set.all()
    fj = job.filejob_set
    analysis = jj.get_job_analysis(job)
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
            'newname': sfile.filename,
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
    if hasattr(sfile, 'analysisresultfile'):
        info['analyses'].append(sfile.analysisresultfile.analysis_id)
    return JsonResponse(info)


def get_nr_raw_mzml_files(files, info):
    storedfiles = {'raw': files.filter(filetype_id=settings.RAW_SFGROUP_ID).count(),
                   'mzML': files.filter(filetype_id=settings.MZML_SFGROUP_ID, 
                                        purged=False, checked=True).count(),
                   'refined_mzML': files.filter(filetype_id=settings.REFINEDMZML_SFGROUP_ID,
                                                purged=False, checked=True).count()}
    info.update({'refinable': False, 'mzmlable': 'ready'})
    if storedfiles['mzML'] == storedfiles['raw']:
        info['mzmlable'] = False
        if 'refine_mzmls' in [x['name'] for x in info['jobs']]:
            info['refinable'] = 'blocked'
        elif not storedfiles['refined_mzML']:
            info['refinable'] = 'ready'
        elif storedfiles['refined_mzML'] != storedfiles['raw']:
            info['refinable'] = 'partly'
    elif 'convert_dataset_mzml' in [x['name'] for x in info['jobs']]:
        info['mzmlable'] = 'blocked'
    return storedfiles, info


def fetch_dset_details(dset):
    dsjobs = filemodels.FileJob.objects.exclude(job__state=jj.Jobstates.DONE).filter(
        storedfile__rawfile__datasetrawfile__dataset_id=dset.id).select_related('job')
    info = {'jobs': [unijob for unijob in
                    {x.job.id: {'name': x.job.funcname, 'state': x.job.state,
                                'retry': jj.is_job_retryable_ready(x.job), 'id': x.job.id,
                                'time': x.job.timestamp} for x in dsjobs}.values()]}
    # FIXME add more datatypes and microscopy is hardcoded
    raws = filemodels.RawFile.objects.filter(datasetrawfile__dataset_id=dset.id)
    info['nrrawfiles'] = raws.count()
    info['storage_loc'] = dset.storage_loc
    info['owners'] = {x.user_id: x.user.username for x in dset.datasetowner_set.select_related('user').all()}
    info['owner_to_add'] = ''
    try:
        info['qtype'] = {'name': dset.quantdataset.quanttype.name, 
                         'short': dset.quantdataset.quanttype.shortname}
    except dsmodels.QuantDataset.DoesNotExist:
        info['qtype'] = False
    nonms_dtypes = {x.id: x.name for x in dsmodels.Datatype.objects.all()
                    if x.name in ['microscopy']}
    files = filemodels.StoredFile.objects.select_related('rawfile__producer', 'filetype').filter(
        rawfile__datasetrawfile__dataset_id=dset.id)
    if dset.datatype_id not in nonms_dtypes:
        nrstoredfiles, info = get_nr_raw_mzml_files(files, info)
    else:
        nrstoredfiles = {nonms_dtypes[dset.datatype_id]: files.filter(filetype_id=settings.RAW_SFGROUP_ID).count()}
    info['instruments'] = list(set([x.rawfile.producer.shortname for x in files]))
    info['nrstoredfiles'] = nrstoredfiles
    info['nrbackupfiles'] = filemodels.SwestoreBackedupFile.objects.filter(
        storedfile__rawfile__datasetrawfile__dataset_id=dset.id).count()
    info['storage_location'] = dset.storage_loc
    info['compstates'] = {x.dtcomp.component.name: x.state for x in
                          dsmodels.DatasetComponentState.objects.filter(
                              dataset_id=dset.id).select_related(
                                  'dtcomp__component')}
    return info


@login_required
def create_mzmls(request, dataset_id):
    if dsmodels.Dataset.objects.filter(pk=dataset_id, deleted=False).count():
        jj.create_dataset_job('convert_dataset_mzml', dataset_id)
    return HttpResponse()


@login_required
def refine_mzmls(request, dataset_id):
    """Creates a job that runs the workflow with the latest version of the mzRefine containing NXF repo.
    Jobs and analysis entries are not created for dsets with full set of refined mzmls (403)."""
    # FIXME get analysis if it does exist, in case someone reruns?
    # Check if files lack refined mzMLs
    nr_refined = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=dataset_id, filetype_id=settings.REFINEDMZML_SFGROUP_ID, checked=True).count()
    nr_mzml = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset_id=dataset_id, filetype_id=settings.MZML_SFGROUP_ID)
    if nr_mzml == nr_refined:
        return HttpResponseForbidden()
    dset = dsmodels.Dataset.objects.select_related('quantdataset__quanttype').get(pk=dataset_id)
    analysis = anmodels.Analysis(user_id=request.user.id, name='refine_dataset_{}'.format(dataset_id))
    analysis.save()
    if dsmodels.Dataset.objects.filter(pk=dataset_id, deleted=False).count():
        jj.create_dataset_job('refine_mzmls', dataset_id, analysis.id, settings.MZREFINER_NXFWFV_ID, 
                              settings.MZREFINER_FADB_ID, dset.quantdataset.quanttype.shortname)
    return HttpResponse()


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
        return HttpResponseForbidden()
