from datetime import timedelta, datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from collections import OrderedDict

from datasets import models as dsmodels
from datasets import jobs as dsjobs
from rawstatus import models as filemodels
from jobs import jobs
from jobs import models as jm


@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {'username': request.user.username}
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
    query |= Q(user__username__icontains=searchterms[0])
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
        subquery |= Q(user__username__icontains=term)
        try:
            float(term)
        except ValueError:
            pass
        else:
            subquery |= Q(prefractionationdataset__hiriefdataset__hirief__start=term)
            subquery |= Q(prefractionationdataset__hiriefdataset__hirief__end=term)
        query &= subquery
    dbdsets = dsmodels.Dataset.objects.filter(query)
    return JsonResponse({'dsets': populate_dset(dbdsets, request.user)})


@login_required
def show_datasets(request):
    if 'dsids' in request.GET:
        dsids = request.GET['dsids'].split(',')
        dbdsets = dsmodels.Dataset.objects.filter(pk__in=dsids)
    else:
        # last month datasets of a user
        dbdsets = dsmodels.Dataset.objects.filter(user_id=request.user.id,
                                                  date__gt=datetime.today() - timedelta(30))
    return JsonResponse({'dsets': populate_dset(dbdsets, request.user)})


def populate_dset(dbdsets, user):
    jobs = {}
    for entry in jm.Job.objects.filter(
            filejob__storedfile__rawfile__datasetrawfile__dataset_id__in=dbdsets):
        try:
            jobs[job.filejob.storedfile.rawfile.datasetrawfile.dataset_id].add(job.state)
        except KeyError:
            jobs[job.filejob.storedfile.rawfile.datasetrawfile.dataset_id] = {job.state}
    dsets = OrderedDict()
    for dataset in dbdsets.select_related('runname__experiment__project',
                                          'prefractionationdataset'):
        jobstates = list(jobs[dataset.id]) if dataset.id in jobs else []
        dsets[dataset.id] = {
            'id': dataset.id,
            'own': dataset.user_id == user.id,
            'usr': dataset.user.username,
            'proj': dataset.runname.experiment.project.name,
            'exp': dataset.runname.experiment.name,
            'run': dataset.runname.name,
            'dtype': dataset.datatype.name,
            'jobstates': jobstates,
            'is_corefac': dataset.runname.experiment.project.corefac,
            'details': False,
            'selected': False,
        }
        if hasattr(dataset, 'prefractionationdataset'):
            pf = dataset.prefractionationdataset
            dsets[dataset.id]['prefrac'] = str(pf.prefractionation.name)
            if 'hirief' in pf.prefractionation.name.lower():
                dsets[dataset.id]['hr'] = '{} {}'.format('HiRIEF', str(pf.hiriefdataset.hirief))
    return dsets


# Ds page links to projects/files/analyses
# Project page links to files/analyses/datasets
# Etc CANNOT dynamically code the table too much
# Make three tables and make them share some code but not all

@login_required
def get_dset_info(request, dataset_id):
    info = {}
    nonms_dtypes = {x.id: x.name for x in dsmodels.Datatype.objects.all()
                    if x.name in ['microscopy']}
    dset = dsmodels.Dataset.objects.filter(pk=dataset_id).select_related(
        'runname__experiment__project').get()
    dsjobs = jm.Job.objects.exclude(state=jobs.Jobstates.DONE).filter(
        filejob__storedfile__rawfile__datasetrawfile__dataset_id=dataset_id)
    info['jobs'] = [{'name': x.job.funcname, 'state': x.job.state,
                     'retry': jobs.is_job_retryable(x.job), 'id': x.job.id,
                     'time': x.job.timestamp} for x in dsjobs]
    raws = filemodels.RawFile.objects.filter(datasetrawfile__dataset_id=dataset_id)
    info['nrrawfiles'] = raws.count()
    storedfiles = {}
    files = filemodels.StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dataset_id)
    if dset.datatype_id not in nonms_dtypes:
        storedfiles['raw'] = files.filter(filetype='raw').count()
        storedfiles['mzML'] = files.filter(filetype='mzml', checked=True).count()
        if storedfiles['mzML'] == storedfiles['raw']:
            info['mzmlable'] = False
        elif 'convert_mzml' in [x.name for x in info['jobs']]:
            info['mzmlable'] = 'blocked'
        else:
            info['mzmlable'] = 'ready'
    else:
        storedfiles[nonms_dtypes[dset.datatype_id]] = files.filter(filetype='raw').count()
    info['nrstoredfiles'] = storedfiles
    info['nrbackupfiles'] = filemodels.SwestoreBackedupFile.objects.filter(
        storedfile__rawfile__datasetrawfile__dataset_id=dataset_id).count()
    info['storage_location'] = dset.storage_loc
    info['compstates'] = {x.dtcomp.component.name: x.state for x in
                          dsmodels.DatasetComponentState.objects.filter(
                              dataset_id=dataset_id).select_related(
                                  'dtcomp__component')}
    return JsonResponse(info)


@login_required
def create_mzmls(request, dataset_id):
    jobs.create_dataset_job('convert_dataset_mzml', dataset_id)
    return HttpResponse()
