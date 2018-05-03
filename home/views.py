from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
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
def show_datasets(request):
    # FIXME this should be called with ds_id or a search query
    if 'dsets' in request.GET:
        dsets = [int(x) for x in request.GET['dsets'].split(',')]
        return get_multidset_info(dsets)
    response = {
        'components': [x.name for x in dsmodels.DatasetComponent.objects.all()]
    }
    dsets = OrderedDict()
    jobs = {}
    for entry in jm.Job.objects.filter(filejob__storedfile__rawfile__datasetrawfile__dataset_id__in=dsets):
        try:
            jobs[job.filejob.storedfile.rawfile.datasetrawfile.dataset_id].add(job.state)
        except KeyError:
            jobs[job.filejob.storedfile.rawfile.datasetrawfile.dataset_id] = {job.state}
    for dataset in dsmodels.Dataset.objects.select_related(
            'runname__experiment__project', 'prefractionationdataset'):
        jobstates = list(jobs[dataset.id]) if dataset.id in jobs else []
        dsets[dataset.id] = {
            'id': dataset.id,
            'own': dataset.user_id == request.user.id,
            'usr': dataset.user.username,
            'proj': dataset.runname.experiment.project.name,
            'exp': dataset.runname.experiment.name,
            'run': dataset.runname.name,
            'dtype': dataset.datatype.name,
            'is_corefac': dataset.runname.experiment.project.corefac,
            'jobstates': jobstates,
            'details': False,
            'selected': False,
        }
        if hasattr(dataset, 'prefractionationdataset'):
            pf = dataset.prefractionationdataset
            dsets[dataset.id]['prefrac'] = str(pf.prefractionation.name)
            if 'hirief' in pf.prefractionation.name.lower():
                dsets[dataset.id]['hr'] = '{} {}'.format('HiRIEF', str(pf.hiriefdataset.hirief))
    response['dsets'] = dsets
    return JsonResponse(response)

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
