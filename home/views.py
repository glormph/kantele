from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from collections import OrderedDict

from datasets import models as dsmodels
from datasets import jobs as dsjobs
from rawstatus import models as filemodels
from jobs import jobs


@login_required
def home(request):
    """Returns home view with Vue apps that will separately request"""
    context = {'username': request.user.username}
    return render(request, 'home/home.html', context)


@login_required
def show_datasets(request):
    if 'dsets' in request.GET:
        dsets = [int(x) for x in request.GET['dsets'].split(',')]
        return get_multidset_info(dsets)
    response = {
        'components': [x.name for x in dsmodels.DatasetComponent.objects.all()]
    }
    dsets = OrderedDict()
    for dcst in dsmodels.DatasetComponentState.objects.select_related(
            'dataset__runname__experiment__project', 'dtcomp__component',
            'dataset__prefractionationdataset'):
        try:
            dsets[dcst.dataset.id][dcst.dtcomp.component.name] = dcst.state
        except KeyError:
            dsets[dcst.dataset.id] = {
                'id': dcst.dataset.id,
                'own': dcst.dataset.user_id == request.user.id,
                'usr': dcst.dataset.user.username,
                'proj': dcst.dataset.runname.experiment.project.name,
                'exp': dcst.dataset.runname.experiment.name,
                'run': dcst.dataset.runname.name,
                'dtype': dcst.dataset.datatype.name,
                'jobs': [],
                'selected': False,
                dcst.dtcomp.component.name: dcst.state,
            }
            if hasattr(dcst.dataset, 'prefractionationdataset'):
                pf = dcst.dataset.prefractionationdataset
                dsets[dcst.dataset.id]['prefrac'] = str(pf.prefractionation.name)
                if 'hirief' in pf.prefractionation.name.lower():
                    dsets[dcst.dataset.id]['hr'] = '{} {}'.format('HiRIEF', str(pf.hiriefdataset.hirief))
    for dsjob in dsmodels.DatasetJob.objects.select_related('job').exclude(job__state=jobs.Jobstates.DONE):
        dsets[dsjob.dataset_id]['jobs'].append({'name': dsjob.job.funcname, 'state': dsjob.job.state})
    response['dsets'] = dsets
    return JsonResponse(response)


@login_required
def get_dset_info(request, dataset_id):
    info = {'num_dsets': 1}
    nonms_dtypes = {x.id: x.name for x in dsmodels.Datatype.objects.all()
                    if x.name in ['microscopy']}
    files = filemodels.StoredFile.objects.filter(
        rawfile__datasetrawfile__dataset_id=dataset_id)
    dset = dsmodels.Dataset.objects.filter(pk=dataset_id).select_related(
        'runname__experiment__project', 'datatype').get()
    raws = filemodels.RawFile.objects.filter(datasetrawfile__dataset_id=dataset_id)
    info['rawfiles'] = [x.name for x in raws]
    storedfiles = {}
    primaryfiles = [x.filename for x in files if x.filetype == 'raw']
    if dset.datatype_id not in nonms_dtypes:
        storedfiles['raw'] = primaryfiles
        storedfiles['mzML'] = [x.filename for x in files if x.filetype == 'mzml'
                               and x.checked]
    else:
        storedfiles[nonms_dtypes[dset.datatype_id]] = primaryfiles
    info['storedfiles'] = storedfiles
    info['backupfiles'] = [x.id for x in filemodels.SwestoreBackedupFile.objects.filter(
        storedfile__rawfile__datasetrawfile__dataset_id=dataset_id)]
    info['dset'] = {'id': dset.id, 'type': dset.datatype.name,
                    'is_corefac': dset.runname.experiment.project.corefac,
                    'storage_location': dset.storage_loc,
                    'project': dset.runname.experiment.project.name,
                    'experiment': dset.runname.experiment.name,
                    'runname': dset.runname.name,
                    'compstates': {x.dtcomp.component.name: x.state for x in
                                   dsmodels.DatasetComponentState.objects.filter(
                                       dataset_id=dataset_id).select_related(
                                           'dtcomp__component')}
                    }
    dsjobs = dsmodels.DatasetJob.objects.select_related('job').filter(
        dataset_id=dataset_id).exclude(job__state=jobs.Jobstates.DONE)
    info['jobnames'] = [x.job.funcname for x in dsjobs]
    info['jobs'] = [{'name': x.job.funcname, 'state': x.job.state,
                     'retry': jobs.is_job_retryable(x.job), 'id': x.job.id,
                     'time': x.job.timestamp} for x in dsjobs]
    return JsonResponse(info)


@login_required
def create_mzmls(request, dataset_id):
    jobs.create_dataset_job('convert_mzml', dataset_id)
    return HttpResponse()
