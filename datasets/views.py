import json
import re
import os
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import (JsonResponse, HttpResponse, HttpResponseNotFound,
                         HttpResponseForbidden)
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.utils import timezone

from kantele import settings
from datasets import models
from rawstatus import models as filemodels
from jobs.jobs import create_job


INTERNAL_PI_PK = 1
COMPSTATE_OK = 'ok'
COMPSTATE_NEW = 'new'
COMPSTATE_INCOMPLETE = 'incomplete'


@login_required
def new_dataset(request):
    """Returns dataset view with JS app"""
    context = {'dataset_id': 'false', 'newdataset': True, 'is_owner': 'true'}
    return render(request, 'datasets/dataset.html', context)



@login_required
def show_dataset(request, dataset_id):
    try:
        dset = models.Dataset.objects.filter(purged=False, pk=dataset_id).select_related(
            'runname__experiment__project').get()
    except models.Dataset.DoesNotExist:
        return HttpResponseNotFound()
    context = {'dataset_id': dataset_id, 'newdataset': False,
               'is_owner': {True: 'true', False: 'false'}[
                   check_ownership(request.user, dset)]}
    return render(request, 'datasets/dataset.html', context)


@login_required
def get_species(request):
    if 'q' in request.GET:
        query = Q(popname__icontains=request.GET['q'])
        query |= Q(linnean__icontains=request.GET['q'])
        return JsonResponse({x.id: {'id': x.id, 'linnean': x.linnean, 'name': x.popname} 
                for x in models.Species.objects.filter(query)})
    else:
        return JsonResponse({x.species.id: {'id': x.species.id, 'linnean': x.species.linnean, 
            'name': x.species.popname} for x in 
            models.DatasetSpecies.objects.all().distinct('species').select_related('species')})


@login_required
def dataset_info_nods(request):
    return dataset_info(request, False)


@login_required
def dataset_info(request, dataset_id):
    response_json = {'projdata': empty_dataset_json(), 'dsinfo': {}}
    if dataset_id:
        try:
            dset = models.Dataset.objects.select_related(
                'runname__experiment__project__projtype', 'datatype',
                'runname__experiment__project__pi',
                'prefractionationdataset__prefractionation',
                'prefractionationdataset__hiriefdataset',
                'prefractionationdataset__prefractionationfractionamount',
                'prefractionationdataset__prefractionationlength'
            ).filter(purged=False, pk=dataset_id).get()
        except models.Dataset.DoesNotExist:
            return HttpResponseNotFound()
        components = models.DatatypeComponent.objects.filter(
            datatype_id=dset.datatype_id).select_related('component')
        project = dset.runname.experiment.project
        response_json['dsinfo'] = {
                'dataset_id': dset.id,
                'experiment_id': dset.runname.experiment_id,
                'runname': dset.runname.name,
                'pi_id': project.pi_id,
                'pi_name': project.pi.name,
                'project_id': project.id,
                'project_name': project.name,
                'ptype_id': project.projtype.ptype_id,
                'datatype_id': dset.datatype_id,
                'storage_location': dset.storage_loc,
            }
        if hasattr(dset, 'prefractionationdataset'):
            response_json['dsinfo'].update(pf_dataset_info_json(
                dset.prefractionationdataset))
        if dset.runname.experiment.project.projtype.ptype_id != settings.LOCAL_PTYPE_ID:
            mail = models.ExternalDatasetContact.objects.get(dataset_id=dset.id)
            response_json['dsinfo'].update({'externalcontactmail': mail.email})
    return JsonResponse(response_json)


@login_required
def dataset_files_nods(request):
    return dataset_files(request, False)


@login_required
def dataset_files(request, dataset_id):
    response_json = empty_files_json()
    if dataset_id:
        if not models.Dataset.objects.filter(purged=False, pk=dataset_id).count():
            return HttpResponseNotFound()
        ds_files = models.DatasetRawFile.objects.select_related(
                'rawfile__producer').filter(dataset_id=dataset_id).order_by('rawfile__date')
        response_json.update({
            'dsfn_order': [x.rawfile_id for x in ds_files],
            'datasetFiles':
            {x.rawfile_id:
              {'id': x.rawfile_id, 'name': x.rawfile.name, 'associd': x.id,
               'instrument': x.rawfile.producer.name,
               'size': round(x.rawfile.size / (2**20), 1),
               'date': x.rawfile.date.timestamp() * 1000, 'checked': False} for x in ds_files}})
    return JsonResponse(response_json)


@login_required
def dataset_acquisition_nods(request):
    return dataset_acquisition(request, False)


@login_required
def dataset_acquisition(request, dataset_id):
    response_json = empty_acquisition_json()
    if dataset_id:
        if not models.Dataset.objects.filter(purged=False, pk=dataset_id).count():
            return HttpResponseNotFound()
        try:
            response_json['dsinfo']['operator_id'] = models.OperatorDataset.objects.get(
                    dataset_id=dataset_id).operator_id

            response_json['dsinfo']['rp_length'] = models.ReversePhaseDataset.objects.get(
                    dataset_id=dataset_id).length
        except models.OperatorDataset.DoesNotExist:
            return JsonResponse(response_json)
        except models.ReversePhaseDataset.DoesNotExist:
            response_json['dsinfo']['dynamic_rp'] = True
            response_json['dsinfo']['rp_length'] = ''
        get_admin_params_for_dset(response_json['dsinfo'], dataset_id, 'acquisition')
    return JsonResponse(response_json)


@login_required
def dataset_sampleprep_nods(request):
    return dataset_sampleprep(request, False)


@login_required
def dataset_sampleprep(request, dataset_id):
    response_json = empty_sampleprep_json()
    if dataset_id:
        dset = models.Dataset.objects.filter(purged=False, pk=dataset_id).select_related('runname__experiment')
        response_json['samples'] = {fn.id: {'model': '', 'newprojsample': ''} 
                for fn in models.DatasetRawFile.objects.filter(dataset_id=dataset_id)}
        if not dset:
            return HttpResponseNotFound()
#        response_json['projsamples'] = {x.id: x.sample for x in models.ProjectSample.objects.filter(project_id=dset.get().runname.experiment.project_id)}
        try:
            qtype = models.QuantDataset.objects.filter(
                dataset_id=dataset_id).select_related('quanttype').get()
        except models.QuantDataset.DoesNotExist:
            return JsonResponse(response_json)
        enzymes_used = {x.enzyme_id for x in 
                models.EnzymeDataset.objects.filter(dataset_id=dataset_id)}
        response_json['no_enzyme'] = True
        for enzyme in response_json['enzymes']:
            if enzyme['id'] in enzymes_used:
                enzyme['checked'] = True
                response_json['no_enzyme'] = False
        qtid = qtype.quanttype_id
        response_json['quanttype'] = qtid
        if qtype.quanttype.name == 'labelfree':
            qfiles = models.QuantSampleFile.objects.filter(
                rawfile__dataset_id=dataset_id)
            if len(set([x.projsample_id for x in qfiles])) == 1:
                response_json['labelfree_singlesample']['model'] = str(qfiles[0].projsample_id)
            else:
                response_json['labelfree_multisample'] = True
            response_json['samples'] = {fn.rawfile_id: {'model': str(fn.projsample_id), 'newprojsample': ''}
                                        for fn in qfiles}
        else:
            response_json['quants'][qtid]['chans'] = [] # resetting from empty sampleprep to re-populate
            for qsc in models.QuantChannelSample.objects.filter(
                    dataset_id=dataset_id).select_related('channel__channel'):
                response_json['quants'][qtid]['chans'].append(
                    {'id': qsc.channel.id, 'name': qsc.channel.channel.name,
                     'model': str(qsc.projsample_id), 'newprojsample': '', 'qcsid': qsc.id})
            # Trick to sort N before C:

            response_json['quants'][qtid]['chans'].sort(key=lambda x: x['name'].replace('N', 'A'))
        # species for dset and mostused ones TODO make sample specific
        response_json['species'] = [{'id': x.species.id, 'linnean': x.species.linnean, 'name': x.species.popname} 
                for x in models.DatasetSpecies.objects.select_related('species').filter(dataset_id=dataset_id)]
        #########

        get_admin_params_for_dset(response_json, dataset_id, 'sampleprep')
    return JsonResponse(response_json)


@login_required
def show_pooled_lc_nods(request):
    return show_pooled_lc(request, False)


@login_required
def show_pooled_lc(request, dataset_id):
    response_json = {'quants': get_empty_isoquant()}
    if dataset_id:
        try:
            qtype = models.QuantDataset.objects.filter(
                dataset_id=dataset_id).get()
        except models.QuantDataset.DoesNotExist:
            pass
        else:
            response_json['quanttype'] = qtype.quanttype_id
    return JsonResponse(response_json)


@login_required
def labelcheck_samples_nods(request):
    labelcheck_samples(request, False)


@login_required
def labelcheck_samples(request, dataset_id):
    response_json = {
            'quants': get_empty_isoquant(),
#            'projsamples': {x.id: {'name': x.sample, 'id': x.id} for x in 
#                models.ProjectSample.objects.filter(project_id=dset.runname.experiment.project_id)},
            }
    if dataset_id:
        dset = models.Dataset.objects.select_related('runname__experiment').get(pk=dataset_id)
        response_json = {
                'quants': get_empty_isoquant(),
                'samples': {fn.id: {'model': '', 'channel': '', 'newprojsample': '', 'channelname': '', 'samplename': ''} 
    #            'projsamples': {x.id: {'name': x.sample, 'id': x.id} for x in 
    #                models.ProjectSample.objects.filter(project_id=dset.runname.experiment.project_id)},
                    for fn in models.DatasetRawFile.objects.filter(dataset_id=dataset_id)}
                }
        for qt, q in response_json['quants'].items():
            q['chanorder'] = [ch['id'] for ch in q['chans']]
            q['chans'] = {ch['id']: ch for ch in q['chans']}
        ### Now return if no LC data stored yet
        try:
            qtype = models.QuantDataset.objects.filter(
                dataset_id=dataset_id).get()
        except models.QuantDataset.DoesNotExist:
            return JsonResponse(response_json)
        else:
            response_json['quanttype'] = qtype.quanttype_id
        for qfcs in models.QuantFileChannelSample.objects.select_related(
                'channel__channel', 'projsample').filter(dsrawfile__dataset_id=dataset_id):
            response_json['samples'][qfcs.dsrawfile_id] = {
                    'qfcsid': qfcs.id, 'channel': qfcs.channel_id, 
                    'channelname': qfcs.channel.channel.name, 
                    'sample': qfcs.projsample_id,
                    'samplename': qfcs.projsample.sample,
                    'newprojsample': ''}
    return JsonResponse(response_json)


@login_required
def save_projsample(request):
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    dset = models.Dataset.objects.select_related(
            'runname__experiment').get(purged=False, pk=data['dataset_id'])
    proj_id = dset.runname.experiment.project_id
    psample = models.ProjectSample(sample=data['samplename'], project_id=proj_id)
    with transaction.atomic():
        try:
            psample.save()
        except IntegrityError:
            print('Not so fast, proj sample saver, this alreasdy exusts')
            psample = False
    if not psample:     
        psample = models.ProjectSample.objects.get(sample=data['samplename'], project_id=proj_id)
    newprojsamples = {x.id: x.sample for x in models.ProjectSample.objects.filter(project_id=proj_id)}
    return JsonResponse({'projsamples': newprojsamples, 'psname': psample.sample, 'psid': str(psample.id)})


@login_required
def get_datatype_components(request, datatype_id):
    dtcomps = models.DatatypeComponent.objects.filter(datatype_id=datatype_id).select_related('component')
    return JsonResponse({'dt_id': datatype_id, 'components': [x.component.name for x in dtcomps]})


def get_admin_params_for_dset(response, dset_id, category):
    """Fetches all stored param values for a dataset and returns nice dict"""
    stored_data, oldparams, newparams = {}, {}, {}
    params = response['params']
    params_saved = False
    for p in models.SelectParameterValue.objects.filter(
            dataset_id=dset_id,
            value__param__category__labcategory=category).select_related(
            'value__param__category'):
        params_saved = True
        if p.value.param.active:
            fill_admin_selectparam(params, p.value, p.value.id)
        else:
            fill_admin_selectparam(oldparams, p.value, p.value.id)
    for p in models.CheckboxParameterValue.objects.filter(
            dataset_id=dset_id,
            value__param__category__labcategory=category).select_related(
            'value__param__category'):
        params_saved = True
        if p.value.param.active:
            fill_admin_checkboxparam(params, p.value, p.value.id)
        else:
            fill_admin_checkboxparam(oldparams, p.value, p.value.id)
    for p in models.FieldParameterValue.objects.filter(
            dataset_id=dset_id,
            param__category__labcategory=category).select_related(
            'param__category'):
        params_saved = True
        if p.param.active:
            fill_admin_fieldparam(params, p.param, p.value)
        else:
            fill_admin_fieldparam(oldparams, p.param, p.value)
    if not params_saved:
        # not saved for this dset id so dont return the params
        return
    # Parse new params (not filled in in dset), old params (not active anymore)
    # use list comprehension so no error: dict changes during iteration
    for p_id in [x for x in params.keys()]:
        if params[p_id]['model'] == '':
            newparams[p_id] = params.pop(p_id)
    if params_saved:
        response['oldparams'] = [x for x in oldparams.values()]
        response['newparams'] = [x for x in newparams.values()]


def update_dataset(data):
    dset = models.Dataset.objects.filter(pk=data['dataset_id']).select_related(
        'runname__experiment', 'datatype').get()
    if 'newprojectname' in data:
        project = newproject_save(data)
    else:
        project = models.Project.objects.get(pk=data['project_id'])
    if project.id != dset.runname.experiment.project_id:
        # all ds proj samples need new project, either move or duplicate...
        dsraws = dset.datasetrawfile_set.all()
        dspsams = models.ProjectSample.objects.filter(quantchannelsample__dataset=dset).union(
                models.ProjectSample.objects.filter(quantsamplefile__rawfile__in=dsraws),
                models.ProjectSample.objects.filter(quantfilechannelsample__dsrawfile__in=dsraws))
        # Since unions cant be filtered/excluded on, re-query
        dspsams = models.ProjectSample.objects.filter(pk__in=dspsams)
        # Duplicate multi DS projsamples from QCS:
        multipsams = set()
        multidsqcs = models.QuantChannelSample.objects.filter(projsample__in=dspsams).exclude(dataset=dset)
        for qcs in multidsqcs.distinct('projsample'):
            multipsams.add(qcs.projsample_id)
            newpsam = models.ProjectSample(sample=qcs.projsample.sample, project=project)
            newpsam.save()
            models.QuantChannelSample.objects.filter(dataset=dset, projsample=qcs.projsample).update(projsample=newpsam)
        multidsqsf = models.QuantSampleFile.objects.filter(projsample__in=dspsams).exclude(rawfile__in=dsraws)
        for qsf in multidsqsf.distinct('projsample'):
            multipsams.add(qsf.projsample_id)
            newpsam = models.ProjectSample(sample=qsf.projsample.sample, project=project)
            newpsam.save()
            models.QuantSampleFile.objects.filter(rawfile__in=dsraws, projsample=qsf.projsample).update(projsample=newpsam)
        multidsqfcs = models.QuantFileChannelSample.objects.filter(projsample__in=dspsams).exclude(dsrawfile__in=dsraws)
        for qfcs in multidsqfcs.distinct('projsample'):
            multipsams.add(qfcs.projsample_id)
            newpsam = models.ProjectSample(sample=qfcs.projsample.sample, project=project)
            newpsam.save()
            models.QuantFileChannelSample.objects.filter(dsrawfile__in=dsraws, projsample=qfcs.projsample).update(projsample=newpsam)
        # having found multi-dset-psams, now move project_id on non-shared projectsamples
        dspsams.exclude(pk__in=multipsams).update(project=project)

    newexp = False
    if 'newexperimentname' in data:
        experiment = models.Experiment(name=data['newexperimentname'],
                                       project=project)
        experiment.save()
        dset.runname.experiment = experiment
        newexp = True
    else:
        experiment = models.Experiment.objects.get(pk=data['experiment_id'])
        experiment.project_id = project.id
        experiment.save()
        if data['experiment_id'] != dset.runname.experiment_id:
            # another experiment was selected
            newexp = True
            dset.runname.experiment = experiment
    if data['runname'] != dset.runname.name or newexp:
        # Save if new experiment AND/OR new name Runname coupled 1-1 to dataset
        print('Update data')
        dset.runname.name = data['runname']
        dset.runname.save()
    if dset.datatype_id != data['datatype_id']:
        dset.datatype_id = data['datatype_id']
        new_dtcomponents = models.DatatypeComponent.objects.filter(datatype_id=data['datatype_id'])
        existing_dtcstates = models.DatasetComponentState.objects.filter(dataset_id=dset.id)
        existing_dtcstates.delete()
        for dtc in new_dtcomponents:
            try:
                old_dtcs = existing_dtcstates.get(dtcomp__component_id=dtc.component_id)
            except models.DatasetComponentState.DoesNotExist:
                state = COMPSTATE_NEW
            else:
                state = old_dtcs.state
            dtcs = models.DatasetComponentState(dataset=dset, dtcomp=dtc, state=state)
            dtcs.save()
    # update prefrac
    try:
        pfds = models.PrefractionationDataset.objects.filter(
            dataset_id=dset.id).select_related(
            'hiriefdataset', 'prefractionationfractionamount',
            'prefractionationlength').get()
    except models.PrefractionationDataset.DoesNotExist:
        pfds = False
    hrf_id, hiph_id = get_prefrac_ids()
    if not pfds and not data['prefrac_id']:
        pass
    elif not pfds and data['prefrac_id']:
        save_dataset_prefrac(dset.id, data, hrf_id)
    elif pfds and not data['prefrac_id']:
        models.PrefractionationDataset.objects.get(
            dataset_id=data['dataset_id']).delete()
    else:
        update_dataset_prefrac(pfds, data, hrf_id)
    dtype = get_datatype(data['datatype_id'])
    prefrac = get_prefrac(data['prefrac_id'])
    qprot_id = get_quantprot_id()
    new_storage_loc = get_storage_location(project, experiment, dset.runname,
                                           qprot_id, hrf_id, dtype, prefrac,
                                           data)
    if (new_storage_loc != dset.storage_loc and 
            models.DatasetRawFile.objects.filter(dataset_id=dset.id).count()):
        create_job('rename_storage_loc', dset_id=dset.id, srcpath=dset.storage_loc,
                           dstpath=new_storage_loc)
        dset.storage_loc = new_storage_loc
    elif new_storage_loc != dset.storage_loc:
        dset.storage_loc = new_storage_loc
    dset.save()
    if data['ptype_id'] != settings.LOCAL_PTYPE_ID:
        try:
            if dset.externaldatasetcontact.email != data['externalcontact']:
                dset.externaldatasetcontact.email = data['externalcontact']
                dset.externaldatasetcontact.save()
        except models.ExternalDatasetContact.DoesNotExist:
            dset_mail = models.ExternalDatasetContact(dataset=dset,
                    email=data['externalcontact'])
            dset_mail.save()
    return JsonResponse({'dataset_id': dset.id})


def newproject_save(data):
    if 'newpiname' in data:
        pi = models.PrincipalInvestigator(name=data['newpiname'])
        pi.save()
        project = models.Project(name=data['newprojectname'], pi=pi)
    else:
        project = models.Project(name=data['newprojectname'], pi_id=data['pi_id'])
    project.save()
    ptype = models.ProjType(project=project, ptype_id=data['ptype_id'])
    ptype.save()
    return project


def get_prefrac_ids():
    return (models.Prefractionation.objects.get(name__icontains='hirief').id,
            models.Prefractionation.objects.get(name__icontains='high pH').id)
            


def get_quantprot_id():
    return models.Datatype.objects.get(name__icontains='quantitative').id


def get_prefrac(pfid):
    if pfid:
        return models.Prefractionation.objects.get(pk=pfid)
    return False


def get_datatype(dtype_id):
    return models.Datatype.objects.get(pk=dtype_id)


def get_storage_location(project, exp, runname, quantprot_id, hrf_id, dtype,
                         prefrac, postdata):
    subdir = ''
    if postdata['datatype_id'] != quantprot_id:
        subdir = dtype.name
    if prefrac and prefrac.id == hrf_id:
        subdir = os.path.join(subdir, models.HiriefRange.objects.get(
            pk=postdata['hiriefrange']).get_path())
    elif prefrac:
        subdir = os.path.join(prefrac.name)
    subdir = re.sub('[^a-zA-Z0-9_\-\/\.]', '_', subdir)
    if len(subdir):
        subdir = '/{}'.format(subdir)
    if dtype.id in settings.LC_DTYPE_IDS:
        return os.path.join(project.name, exp.name, str(runname.id))
    else:
        return '{}/{}{}/{}'.format(project.name, exp.name, subdir, runname.name)


@login_required
def change_owners(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        dset = models.Dataset.objects.get(pk=data['dataset_id'])
    except models.Dataset.DoesNotExist:
        print('change_owners could not find dataset with that ID {}'.format(data['dataset_id']))
        return JsonResponse({'error': 'Something went wrong trying to change ownership for that dataset'}, status=403)
    if not check_ownership(request.user, dset):
        return HttpResponseForbidden()
    is_already_owner = models.DatasetOwner.objects.filter(dataset_id=dset, user_id=data['owner'])
    if data['op'] == 'add' and not is_already_owner:
        newowner = models.DatasetOwner(dataset=dset, user_id=data['owner'])
        newowner.save()
        return JsonResponse({'result': 'ok'})
    elif data['op'] == 'del' and is_already_owner and dset.datasetowner_set.count() > 1:
        is_already_owner.delete()
        return JsonResponse({'result': 'ok'})
    else:
        return JsonResponse({'result': 'error', 'message': 'Something went wrong trying to change ownership'}, status=500)
    

def get_dataset_owners_ids(dset):
    return [x.user.id for x in dset.datasetowner_set.all()]


def check_ownership(user, dset):
    pt_id = dset.runname.experiment.project.projtype.ptype_id 
    if dset.deleted and not user.is_staff:
        return False
    elif user.id in get_dataset_owners_ids(dset) or user.is_staff:
        return True
    elif pt_id == settings.LOCAL_PTYPE_ID:
        return False
    else:
        try:
            models.UserPtype.objects.get(ptype_id=pt_id, user_id=user.id)
        except models.UserPtype.DoesNotExist:
            return False
    return True


def check_save_permission(dset_id, logged_in_user):
    try:
        dset = models.Dataset.objects.filter(purged=False, pk=dset_id).select_related(
            'runname__experiment__project').get()
    except models.Dataset.DoesNotExist:
        return HttpResponseNotFound()
    else:
        if not check_ownership(logged_in_user, dset):
            return HttpResponseForbidden()
    return False


def get_or_create_px_dset(exp, px_acc, user_id):
    try:
        return models.Dataset.objects.get(
            runname__name=px_acc,
            runname__experiment__project_id=settings.PX_PROJECT_ID)
    except models.Dataset.DoesNotExist:
        project = models.Project.objects.get(pk=settings.PX_PROJECT_ID)
        experiment = models.Experiment(name=exp, project=project)
        experiment.save()
        run = models.RunName(name=px_acc, experiment=experiment)
        run.save()
        data = {'datatype_id': get_quantprot_id(), 'prefrac_id': False,
                'ptype_id': settings.LOCAL_PTYPE_ID}
        return save_new_dataset(data, project, experiment, run, user_id)


def get_or_create_qc_dataset(data):
    qcds = models.Dataset.objects.filter(
        runname__experiment_id=data['experiment_id'],
        runname_id=data['runname_id'])
    if qcds:
        return qcds.get()
    else:
        project = models.Project.objects.get(pk=settings.INSTRUMENT_QC_PROJECT)
        exp = models.Experiment.objects.get(pk=settings.INSTRUMENT_QC_EXP)
        run = models.RunName.objects.get(pk=data['runname_id'])
        data['datatype_id'] = settings.QC_DATATYPE
        data['prefrac_id'] = False
        data['ptype_id'] = settings.LOCAL_PTYPE_ID
        return save_new_dataset(data, project, exp, run, settings.QC_USER_ID)


def save_new_dataset(data, project, experiment, runname, user_id):
    hrf_id, hiph_id = get_prefrac_ids()
    dtype = get_datatype(data['datatype_id'])
    prefrac = get_prefrac(data['prefrac_id'])
    qprot_id = get_quantprot_id()
    dset = models.Dataset(date=timezone.now(),
                          runname_id=runname.id,
                          storage_loc=get_storage_location(
                              project, experiment, runname, qprot_id, hrf_id,
                              dtype, prefrac, data),
                          datatype=dtype)
    dset.save()
    dsowner = models.DatasetOwner(dataset=dset, user_id=user_id)
    dsowner.save()
    if data['prefrac_id']:
        save_dataset_prefrac(dset.id, data, hrf_id)
    if data['ptype_id'] != settings.LOCAL_PTYPE_ID:
        dset_mail = models.ExternalDatasetContact(dataset=dset,
                                                 email=data['externalcontact'])
        dset_mail.save()
    if dset.datatype_id != settings.QC_DATATYPE:
        dtcomp = models.DatatypeComponent.objects.get(datatype_id=dset.datatype_id,
                                                      component__name='definition')
        models.DatasetComponentState.objects.create(dtcomp=dtcomp,
                                                    dataset_id=dset.id,
                                                    state=COMPSTATE_OK)
        models.DatasetComponentState.objects.bulk_create([
            models.DatasetComponentState(
                dtcomp=x, dataset_id=dset.id, state=COMPSTATE_NEW) for x in
            models.DatatypeComponent.objects.filter(
                datatype_id=dset.datatype_id).exclude(
                component__name='definition')])
    return dset


@login_required
def move_project_cold(request):
    data = json.loads(request.body.decode('utf-8'))
    if 'item_id' not in data or not data['item_id']:
        return JsonResponse({'state': 'error', 'error': 'No project specified for retiring'}, status=400)
    projquery = models.Project.objects.filter(pk=data['item_id'], active=True)
    if not projquery:
        return JsonResponse({'state': 'error', 'error': 'Project is retired, purged or never existed'}, status=400)
    # Retiring a project is only allowed if user owns ALL datasets in project or is staff
    dsetowners = models.DatasetOwner.objects.filter(dataset__runname__experiment__project_id=data['item_id'], dataset__purged=False).select_related('dataset')
    if dsetowners.filter(user=request.user).count() != dsetowners.distinct('dataset').count() and not request.user.is_staff:
        return JsonResponse({'state': 'error', 'error': 'User has no permission to retire this project, does not own all datasets in project'}, status=403)
    # Cold store all datasets, delete them from active
    result = {'errormsgs': []}
    for dso in dsetowners.distinct('dataset'):
        archived = archive_dataset(dso.dataset)
        if archived['state'] == 'error':
            result.update({'state': 'error', 'error': 'Not all datasets could be updated.'})
            result['errormsgs'].append(archived['error'])
    # if any dataset cannot be cold stored, report it, do not mark proj as retired
    if result['errormsgs']:
        projquery.update(active=True)
        result['error'] = '{} Errors: {}'.format(result['error'], '; '.join(result.pop('errormsgs')))
        return JsonResponse(result, status=500)
    else:
        projquery.update(active=False)
        return JsonResponse({})


@login_required
def move_project_active(request):
    data = json.loads(request.body.decode('utf-8'))
    if 'item_id' not in data or not data['item_id']:
        return JsonResponse({'state': 'error', 'error': 'No project specified for reactivating'}, status=400)
    projquery = models.Project.objects.filter(pk=data['item_id'], active=False)
    if not projquery:
        return JsonResponse({'state': 'error', 'error': 'Project is already active, or does not exist'}, status=403)
    # Reactivating a project is only allowed if user owns ALL datasets in project or is staff
    dsetowners = models.DatasetOwner.objects.filter(dataset__runname__experiment__project_id=data['item_id'], dataset__purged=False).select_related('dataset')
    if dsetowners.filter(user=request.user).count() != dsetowners.distinct('dataset').count() and not request.user.is_staff:
        return JsonResponse({'state': 'error', 'error': 'User has no permission to reactivate this project, does not own all datasets in project'}, status=403)
    # Reactivate all datasets
    result = {'errormsgs': []}
    for dso in dsetowners.distinct('dataset'):
        reactivated = reactivate_dataset(dso.dataset)
        if reactivated['state'] == 'error':
            result.update({'state': 'error', 'error': 'Not all project datasets could be reactivated.'})
            result['errormsgs'].append(reactivated['error'])
        else:
            # if ANY dataset gets reactivated, project is active
            projquery.update(active=True)
    if result['errormsgs']:
        result['error'] = '{} Errors: {}'.format(result['error'], '; '.join(result.pop('errormsgs')))
        return JsonResponse(result, status=500)
    else:
        return JsonResponse({})


@login_required
def purge_project(request):
    """Deletes project datasets (not analyses) from disk, only leaving backup copies."""
    data = json.loads(request.body.decode('utf-8'))
    if 'item_id' not in data or not data['item_id']:
        return JsonResponse({'state': 'error', 'error': 'No project specified for reactivating'}, status=400)
    projquery = models.Project.objects.filter(pk=data['item_id'], active=False)
    if not projquery:
        return JsonResponse({'state': 'error', 'error': 'Project does not exist or is still active'}, status=403)
    dsetowners = models.DatasetOwner.objects.filter(dataset__runname__experiment__project_id=data['item_id'], dataset__purged=False).select_related('dataset')
    if not request.user.is_staff:
        return JsonResponse({'state': 'error', 'error': 'User has no permission to purge this project, must be staff'}, status=403)
    result = {'errormsgs': []}
    for dso in dsetowners.distinct('dataset'):
        purged = delete_dataset_from_cold(dso.dataset)
        if purged['state'] == 'error':
            result.update({'state': 'error', 'error': 'Not all project datasets could be purged'})
            result['errormsgs'].append(purged['error'])
    # if any dataset cannot be purged, report it, do not mark proj as purged
    if result['errormsgs']:
        result['error'] = '{} Errors: {}'.format(result['error'], '; '.join(result.pop('errormsgs')))
        return JsonResponse(result, status=500)
    else:
        projquery.update(active=False)
        return JsonResponse({})


def get_dset_storestate(dset, dsfiles=False):
    if not dsfiles:
        dsfiles = filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset=dset)
    dsfiles = dsfiles.exclude(mzmlfile__isnull=False)
    dsfc = dsfiles.count()
    if dsfc == 0:
        return 'empty'
    coldfiles = dsfiles.filter(pdcbackedupfile__isnull=False, pdcbackedupfile__deleted=False, pdcbackedupfile__success=True)
    if dsfiles.filter(checked=True, deleted=False).count() == dsfc == coldfiles.count():
        storestate = 'complete'
    elif dsfiles.filter(checked=True, deleted=False).count() == dsfc:
        storestate = 'active-only'
    elif coldfiles.count() == dsfc:
        storestate = 'cold'
    elif dsfiles.filter(purged=True).count() == dsfc and dsfiles.filter(pdcbackedupfile__deleted=True) == dsfiles.filter(pdcbackedupfile__isnull=False).count():
        storestate = 'purged'
    elif dsfiles.filter(pdcbackedupfile__deleted=True).count() > 0:
        storestate = 'broken'
    elif dsfiles.filter(checked=False) or dsfiles.filter(servershare__name=settings.TMPSHARENAME):
        storestate = 'new'
    else:
        storestate = 'unknown'
    return storestate


def archive_dataset(dset):
    # FIXME dataset reactivating and archiving reports error when ok and vv? I mean, if you click archive and reactivate quickly, you will get error (still in active storage), and also in this func, storestate is not updated at same time as DB (it is result of jobs)
    storestate = get_dset_storestate(dset)
    if storestate == 'purged':
        return {'state': 'error', 'error': 'Cannot archive dataset, already purged'}
    elif storestate == 'broken':
        return {'state': 'error', 'error': 'Cannot archive dataset, files missing on active storage'}
    elif storestate == 'new':
        return {'state': 'error', 'error': 'Cannot archive new dataset'}
    elif storestate == 'unknown':
        return {'state': 'error', 'error': 'Cannot archive dataset with unknown storage state'}
    if storestate == 'active-only':
        create_job('backup_dataset', dset_id=dset.id)
    if storestate != 'empty':
        create_job('delete_active_dataset', dset_id=dset.id)
        create_job('delete_empty_directory', sf_ids=[x.id for x in filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset=dset)])
    dset.deleted, dset.purged = True, False
    dset.save()
    return {'state': 'ok', 'error': 'Dataset queued for archival'}


def reactivate_dataset(dset):
    storestate = get_dset_storestate(dset)
    if storestate == 'purged':
        return {'state': 'error', 'error': 'Cannot reactivate purged dataset'}
    elif storestate == 'broken':
        return {'state': 'error', 'error': 'Cannot reactivate dataset, files missing on active storage'}
    elif storestate == 'new':
        return {'state': 'error', 'error': 'Cannot reactivate new dataset'}
    elif storestate == 'unknown':
        return {'state': 'error', 'error': 'Cannot reactivate dataset with unknown storage state'}
    elif storestate in ['active-only', 'complete']:
        return {'state': 'error', 'error': 'Dataset already in active storage'}
    elif storestate == 'empty':
        dset.deleted, dset.purged, dset.runname.experiment.project.active = False, False, True
        dset.save()
        dset.runname.experiment.project.save()
        return {'state': 'ok', 'error': 'Empty dataset (contains no files) re-activated'}
    elif storestate == 'cold':
        dset.deleted, dset.purged, dset.runname.experiment.project.active = False, False, True
        dset.save()
        dset.runname.experiment.project.save()
        create_job('reactivate_dataset', dset_id=dset.id)
        return {'state': 'ok'}


@login_required
def move_dataset_cold(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        dset = models.Dataset.objects.select_related('runname__experiment__project__projtype').get(pk=data['item_id'])
    except models.Dataset.DoesNotExist:
        return JsonResponse({'error': 'Dataset does not exist'}, status=403)
    if not check_ownership(request.user, dset):
        return JsonResponse({'error': 'Cannot archive dataset, no permission for user'}, status=403)
    archived = archive_dataset(dset)
    if archived['state'] == 'error':
        return JsonResponse(archived, status=500)
    else:
        return JsonResponse(archived)


@login_required
def move_dataset_active(request):
    data = json.loads(request.body.decode('utf-8'))
    try:
        dset = models.Dataset.objects.select_related('runname__experiment__project__projtype').get(pk=data['item_id'])
    except models.Dataset.DoesNotExist:
        return JsonResponse({'error': 'Dataset does not exist'}, status=403)
    if not check_ownership(request.user, dset):
        return JsonResponse({'error': 'Cannot reactivate dataset, no permission for user'}, status=403)
    reactivated_msg = reactivate_dataset(dset)
    if reactivated_msg['state'] == 'error':
        return JsonResponse(reactivated_msg, status=500)
    else:
        return JsonResponse(reactivated_msg)


def delete_dataset_from_cold(dset):
    return {'state': 'error', 'error': 'Cannot permanent delete yet, not implemented'}
    # TODO Should we allow direct purging? the delete from active job is fired anyway
    if not dset.deleted:
        return {'state': 'error', 'error': 'Dataset is not deleted, will not purge'}
    dset.purged = True
    dset.save()
    # Also create delete active job just in case files are lying around
    create_job('delete_active_dataset', dset_id=dset.id)
    create_job('delete_empty_directory', sf_ids=[x.id for x in filemodels.StoredFile.objects.filter(rawfile__datasetrawfile__dataset=dset)])
    storestate = get_dset_storestate(dset)
    if storestate != 'empty':
        create_job('delete_dataset_coldstorage', dset_id=dset.id)
    sfids = [sf.id for dsrf in dset.datasetrawfile_set.select_related('rawfile') for sf in dsrf.rawfile.storedfile_set.all()]
    create_job('delete_empty_directory', sf_ids=sfids)
    return {'state': 'ok', 'error': 'Dataset queued for permanent deletion'}


@login_required
def purge_dataset(request):
    """Deletes dataset from disk, only leaving backup copies."""
    data = json.loads(request.body.decode('utf-8'))
    if not request.user.is_staff:
        return JsonResponse({'error': 'Only admin can purge dataset'}, status=403)
    try:
        dset = models.Dataset.objects.get(pk=data['item_id'])
    except models.Dataset.DoesNotExist:
        return JsonResponse({'error': 'Dataset does not exist'}, status=403)
    purgemsg = delete_dataset_from_cold(dset)
    if purgemsg['state'] == 'error':
        return JsonResponse(purgemsg, status=500)
    else:
        return JsonResponse(purgemsg)


@login_required
def save_dataset(request):
    data = json.loads(request.body.decode('utf-8'))
    if data['dataset_id']:
        user_denied = check_save_permission(data['dataset_id'], request.user)
        if user_denied:
            return user_denied
        print('Updating')
        return update_dataset(data)
    else:
        if 'newprojectname' in data:
            project = newproject_save(data)
        else:
            try:
                project = models.Project.objects.get(pk=data['project_id'], active=True)
            except models.Project.DoesNotExist:
                print('Project to save to is not active')
                return HttpResponseForbidden()
        if data['datatype_id'] in settings.LC_DTYPE_IDS:
            try:
                experiment = models.Experiment.objects.get(project=project, name=settings.LCEXPNAME)
            except models.Experiment.DoesNotExist:
                experiment = models.Experiment(name=settings.LCEXPNAME, project=project)
                experiment.save()
            runname = models.RunName(name=settings.LCEXPNAME, experiment=experiment)
        else:
            if 'newexperimentname' in data:
                experiment = models.Experiment(name=data['newexperimentname'],
                                               project_id=project.id)
                experiment.save()

            elif 'experiment_id' in data:
                experiment = models.Experiment.objects.get(pk=data['experiment_id'])
            runname = models.RunName(name=data['runname'], experiment=experiment)
        runname.save()
        try:
            dset = save_new_dataset(data, project, experiment, runname, request.user.id)
        except IntegrityError:
            print('Cannot save dataset with non-unique location')
            return JsonResponse({'state': 'error', 'error': 'Cannot save dataset, storage location not unique'})
    return JsonResponse({'dataset_id': dset.id})


def save_dataset_prefrac(dset_id, data, hrf_id):
    pfds = models.PrefractionationDataset(
        dataset_id=dset_id, prefractionation_id=data['prefrac_id'])
    pfds.save()
    models.PrefractionationFractionAmount.objects.create(
        pfdataset=pfds, fractions=data['prefrac_amount'])
    if data['prefrac_id'] == hrf_id:
        models.HiriefDataset.objects.create(pfdataset=pfds,
                                            hirief_id=data['hiriefrange'])
    else:
        models.PrefractionationLength.objects.create(
            pfdataset=pfds, length=data['prefrac_length'])


def update_prefrac_len(pfds, data):
    pass


def update_dataset_prefrac(pfds, data, hrf_id):
    if pfds.prefractionation_id != data['prefrac_id']:
        if pfds.prefractionation_id == hrf_id:
            models.HiriefDataset.objects.filter(pfdataset=pfds).delete()
            models.PrefractionationLength.objects.create(
                pfdataset=pfds, length=data['prefrac_length'])
        elif data['prefrac_id'] == hrf_id:
            models.PrefractionationLength.objects.filter(pfdataset=pfds).delete()
            models.HiriefDataset.objects.create(pfdataset=pfds,
                                                hirief_id=data['hiriefrange'])
        else:
            models.PrefractionationLength.objects.filter(pfdataset=pfds).update(
                length=data['prefrac_length'])
        pfds.prefractionation_id = data['prefrac_id']
        pfds.save()
    else:
        if data['prefrac_id'] == hrf_id:
            if pfds.hiriefdataset != data['hiriefrange']:
                pfds.hiriefdataset.hirief_id = data['hiriefrange']
                pfds.hiriefdataset.save()
        else:
            if pfds.prefractionationlength.length != data['prefrac_length']:
                pfds.prefractionationlength.length = data['prefrac_length']
                pfds.prefractionationlength.save()
    # update fr amount if neccessary
    pffa = pfds.prefractionationfractionamount
    if (pffa.fractions != data['prefrac_amount']):
        pffa.fractions = data['prefrac_amount']
        pffa.save()


@login_required
def get_project(request, project_id):
    proj = models.Project.objects.select_related('projtype').get(pk=project_id)
    return JsonResponse({
        'id': project_id, 'pi_id': proj.pi_id, 'ptype_id': proj.projtype.ptype_id,
        'projsamples': {x.id: {'name': x.sample, 'id': x.id} for x in models.ProjectSample.objects.filter(project_id=project_id)},
        'experiments': [{'id': x.id, 'name': x.name} for x in 
        models.Experiment.objects.filter(project_id=project_id)]})


def empty_dataset_json():
    edpr = {'projects': {x.id:
        {'name': x.name, 'id': x.id, 'ptype_id': x.projtype.ptype_id,
            'select': False, 'pi_id': x.pi_id} 
        for x in models.Project.objects.select_related('projtype').filter(active=True)},
            'ptypes': [{'name': x.name, 'id': x.id} for x in models.ProjectTypeName.objects.all()],
            'external_pis': {x.id: {'name': x.name, 'id': x.id} for x in
                             models.PrincipalInvestigator.objects.all()},
            'internal_pi_id': INTERNAL_PI_PK,
            'local_ptype_id': settings.LOCAL_PTYPE_ID,
            'datasettypes': [{'name': x.name, 'id': x.id} for x in
                             models.Datatype.objects.filter(public=True)],
            'prefracs': [{'id': x.id, 'name': x.name}
                          for x in models.Prefractionation.objects.all()],
            'hirief_ranges': [{'name': str(x), 'id': x.id}
                              for x in models.HiriefRange.objects.all()]}
    return edpr


def pf_dataset_info_json(pfds):
    resp_json = {'prefrac_id': pfds.prefractionation.id,
                 'prefrac_amount': pfds.prefractionationfractionamount.fractions}
    if hasattr(pfds, 'hiriefdataset'):
        resp_json.update({'hiriefrange': pfds.hiriefdataset.hirief.id})
    else:
        resp_json.update({'prefrac_length': pfds.prefractionationlength.length})
    return resp_json


def get_empty_isoquant():
    quants = {}
    for chan in models.QuantTypeChannel.objects.all().select_related(
            'quanttype', 'channel'):
        if not chan.quanttype.id in quants:
            quants[chan.quanttype.id] = {'id': chan.quanttype.id, 'chans': [],
                                         'name': chan.quanttype.name}
        quants[chan.quanttype.id]['chans'].append({'id': chan.id,
                                                   'name': chan.channel.name,
                                                   'newprojsample': '',
                                                   'model': ''})
        # Trick to sort N before C:
        quants[chan.quanttype.id]['chans'].sort(key=lambda x: x['name'].replace('N', 'A'))
    return quants


def empty_sampleprep_json():
    params = get_dynamic_emptyparams('sampleprep')
    quants = get_empty_isoquant()
    labelfree = models.QuantType.objects.get(name='labelfree')
    quants[labelfree.id] = {'id': labelfree.id, 'name': 'labelfree'}
    return {'params': params, 'quants': quants, 'species': [],
            'labelfree_multisample': False,
            'labelfree_singlesample': {'model': '', 'newprojsample': ''},
            'enzymes': [{'id': x.id, 'name': x.name, 'checked': False}
                for x in models.Enzyme.objects.all()],
            'allspecies': {str(x['species']): {'id': x['species'], 'linnean': x['species__linnean'],
                'name': x['species__popname'], 'total': x['total']} 
                for x in models.DatasetSpecies.objects.all().values('species', 'species__linnean', 'species__popname'
                    ).annotate(total=Count('species__linnean')).order_by('-total')[:5]},
            }


def fill_admin_selectparam(params, p, value=False):
    """Fills params dict with select parameters passed, in proper JSON format
    This takes care of both empty params (for new dataset), filled parameters,
    and old parameters"""
    if p.param.id not in params:
        params[p.param.id] = {'param_id': p.param.id, 'fields': [],
                              'inputtype': 'select', 'title': p.param.title}
    if value:
        # fields is already populated by call to empty params
        params[p.param.id]['model'] = value
    else:
        params[p.param.id]['model'] = ''
        params[p.param.id]['fields'].append({'value': p.id, 'text': p.value})


def fill_admin_checkboxparam(params, p, value=False):
    """Fills params dict with select parameters passed, in proper JSON format
    This takes care of both empty params (for new dataset), filled parameters,
    and old parameters"""
    # param must have a model for ability of checking if it is new param
    # which dataset does not have
    if p.param.id not in params:
        params[p.param.id] = {'param_id': p.param.id, 'fields': [], 'model': True,
                              'inputtype': 'checkbox', 'title': p.param.title}
    if value:
        # fields key is already populated by call to empty params
        for box in params[p.param_id]['fields']:
            if box['value'] == value:
                box['checked'] = True 
    else:
        params[p.param.id]['fields'].append({'checked': False, 'value': p.id, 'text': p.value})


def fill_admin_fieldparam(params, p, value=False):
    """Fills params dict with field parameters passed, in proper JSON format
    This takes care of both empty params (for new dataset), filled parameters,
    and old parameters"""
    params[p.id] = {'param_id': p.id, 'placeholder': p.placeholder,
                    'inputtype': p.paramtype.typename, 'title': p.title}
    params[p.id]['model'] = value if value else ''


def get_dynamic_emptyparams(category):
    params = {}
    for p in models.SelectParameterOption.objects.select_related(
            'param').filter(param__category__labcategory=category):
        if p.param.active:
            fill_admin_selectparam(params, p)
    for p in models.FieldParameter.objects.select_related(
            'paramtype').filter(category__labcategory=category):
        if p.active:
            fill_admin_fieldparam(params, p)
    for p in models.CheckboxParameterOption.objects.select_related(
            'param').filter(param__category__labcategory=category):
        if p.param.active:
            fill_admin_checkboxparam(params, p)
    return params


def empty_acquisition_json():
    return {'dsinfo': {'params': get_dynamic_emptyparams('acquisition')},
            'acqdata': {'operators': [{'id': x.id, 'name': '{} {}'.format(
                x.user.first_name, x.user.last_name)}
                for x in models.Operator.objects.select_related('user').all()]},
            }


@login_required
def find_files(request):
    searchterms = [x for x in request.GET['q'].split(',') if x != '']
    query = Q(name__icontains=searchterms[0])
    query |= Q(producer__name__icontains=searchterms[0])
    for term in searchterms[1:]:
        subquery = Q(name__icontains=term)
        subquery |= Q(producer__name__icontains=term)
        query &= subquery
    newfiles = filemodels.RawFile.objects.filter(query).filter(claimed=False)
    return JsonResponse({
        'newfn_order': [x.id for x in newfiles.order_by('-date')],
        'newFiles': {x.id:
                         {'id': x.id, 'name': x.name, 
                          'size': round(x.size / (2**20), 1),
                          'date': x.date.timestamp() * 1000,
                          'instrument': x.producer.name, 'checked': False}
                         for x in newfiles}})


def empty_files_json():
    newfiles = filemodels.RawFile.objects.select_related('producer').filter(
            claimed=False, date__gt=datetime.now() - timedelta(200))
    return {'instruments': [x.name for x in filemodels.Producer.objects.all()],
            'datasetFiles': [],
            'newfn_order': [x.id for x in newfiles.order_by('-date')],
            'newFiles': {x.id:
                         {'id': x.id, 'name': x.name, 
                          'size': round(x.size / (2**20), 1),
                          'date': x.date.timestamp() * 1000,
                          'instrument': x.producer.name, 'checked': False}
                         for x in newfiles}}


def save_or_update_files(data):
    dset_id = data['dataset_id']
    added_fnids = [x['id'] for x in data['added_files'].values()]
    dset = models.Dataset.objects.get(pk=dset_id)
    if added_fnids:
        models.DatasetRawFile.objects.bulk_create([
            models.DatasetRawFile(dataset_id=dset_id, rawfile_id=fnid)
            for fnid in added_fnids])
        filemodels.RawFile.objects.filter(
            pk__in=added_fnids).update(claimed=True)
        create_job('move_files_storage', dset_id=dset_id, dst_path=dset.storage_loc,
                rawfn_ids=added_fnids)
    removed_ids = [int(x['id']) for x in data['removed_files'].values()]
    if removed_ids:
        models.DatasetRawFile.objects.filter(
            dataset_id=dset_id, rawfile_id__in=removed_ids).delete()
        filemodels.RawFile.objects.filter(pk__in=removed_ids).update(
            claimed=False)
        create_job('move_stored_files_tmp', dset_id=dset_id, fn_ids=removed_ids)
    # If files changed and labelfree, set sampleprep component status
    # to not good. Which should update the tab colour (green to red)
    try:
        qtype = models.Dataset.objects.select_related(
            'quantdataset__quanttype').get(pk=dset_id).quantdataset.quanttype
    except models.QuantDataset.DoesNotExist:
        pass
    else:
        if (added_fnids or removed_ids) and qtype.name == 'labelfree':
            set_component_state(dset_id, 'sampleprep', COMPSTATE_INCOMPLETE)
    if dset.datatype_id != settings.QC_DATATYPE:
        set_component_state(dset_id, 'files', COMPSTATE_OK)


@login_required
def save_files(request):
    """Updates and saves files"""
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    save_or_update_files(data)    
    return JsonResponse({})


def update_acquisition(dset, data):
    if data['operator_id'] != dset.operatordataset.operator_id:
        dset.operatordataset.operator_id = data['operator_id']
        dset.operatordataset.save()
    if not hasattr(dset, 'reversephasedataset'):
        if data['rp_length']:
            models.ReversePhaseDataset.objects.create(dataset_id=dset.id,
                                                      length=data['rp_length'])
    elif not data['rp_length']:
            dset.reversephasedataset.delete()
#            models.ReversePhaseDataset.objects.filter(
#                dataset_id=dset.id).delete()
    elif data['rp_length'] != dset.reversephasedataset.length:
        dset.reversephasedataset.length = data['rp_length']
        dset.reversephasedataset.save()
    update_admin_defined_params(dset, data, 'acquisition')
    return JsonResponse({})


@login_required
def save_acquisition(request):
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    dset_id = data['dataset_id']
    dset = models.Dataset.objects.filter(pk=data['dataset_id']).select_related(
        'operatordataset', 'reversephasedataset').get()
    if hasattr(dset, 'operatordataset'):
        return update_acquisition(dset, data)
    if data['rp_length']:
        models.ReversePhaseDataset.objects.create(dataset_id=dset_id,
                                                  length=data['rp_length'])
    models.OperatorDataset.objects.create(dataset_id=dset_id,
                                          operator_id=data['operator_id'])
    save_admin_defined_params(data, dset_id)
    set_component_state(dset_id, 'acquisition', COMPSTATE_OK)
    return JsonResponse({})


def store_new_channelsamples(data):
    models.QuantChannelSample.objects.bulk_create([
        models.QuantChannelSample(dataset_id=data['dataset_id'],
            projsample_id=chan['model'], channel_id=chan['id'])
        for chan in data['samples']])


def quanttype_switch_isobaric_update(oldqtype, updated_qtype, data, dset_id):
    # switch from labelfree - tmt: remove filesample, create other channels
    if oldqtype == 'labelfree' and updated_qtype:
        print('Switching to isobaric')
        store_new_channelsamples(data)
        models.QuantSampleFile.objects.filter(
            rawfile__dataset_id=dset_id).delete()
    # reverse switch
    elif data['labelfree'] and updated_qtype:
        print('Switching isobaric-labelfree')
        models.QuantChannelSample.objects.filter(dataset_id=dset_id).delete()
    elif not data['labelfree']:
        print('Updating isobaric')
        if updated_qtype:
            print('new quant type found')
            models.QuantChannelSample.objects.filter(
                dataset_id=dset_id).delete()
            store_new_channelsamples(data)
        else:
            print('checking if new samples')
            existing_samples = {x.id: (x.projsample_id, x) for x in 
                models.QuantChannelSample.objects.filter(dataset_id=data['dataset_id'])}
            for chan in data['samples']:
                exis_qcs = existing_samples[chan['qcsid']]
                if chan['model'] != exis_qcs[0]:
                    exis_qcs[1].projsample_id = chan['model']
                    exis_qcs[1].save()
                if chan['id'] != exis_qcs[1].channel_id:
                    exis_qcs[1].channel_id = chan['id']
                    exis_qcs[1].save()


def update_labelcheck(data, qtype):
    dset_id = data['dataset_id']
    if data['quanttype'] != qtype.quanttype_id:
        qtype.quanttype_id = data['quanttype']
        qtype.save()
    # Add any possible new channels 
    oldqfcs = {x.dsrawfile_id: x for x in models.QuantFileChannelSample.objects.filter(dsrawfile__dataset_id=dset_id)}
    for fn in data['filenames']:
        sam = data['samples'][str(fn['associd'])]
        try:
            exis_q = oldqfcs.pop(fn['associd'])
        except KeyError:
            models.QuantFileChannelSample.objects.create(dsrawfile_id=fn, 
                    projsample_id=sam['sample'], channel=sam['channel'])
        else:
            if sam['sample'] != exis_q.projsample_id:
                exis_q.projsample_id = sam['sample']
                exis_q.save()
            if sam['channel'] != exis_q.channel_id:
                exis_q.channel_id = sam['channel']
                exis_q.save()
    # delete non-existing qcfs (files have been popped)
    [qcfs.delete() for qcfs in oldqfcs.values()]


def update_sampleprep(data, qtype):
    dset_id = data['dataset_id']
    new_enzymes = set([x['id'] for x in data['enzymes'] if x['checked']])
    for enzyme in models.EnzymeDataset.objects.filter(dataset_id=dset_id):
        if enzyme.enzyme_id in new_enzymes:
            new_enzymes.remove(enzyme.enzyme_id)
        else:
            enzyme.delete()
    models.EnzymeDataset.objects.bulk_create([models.EnzymeDataset(
        dataset_id=dset_id, enzyme_id=x) for x in new_enzymes])
    oldqtype = qtype.quanttype.name
    updated_qtype = False
    if data['quanttype'] != qtype.quanttype_id:
        qtype.quanttype_id = data['quanttype']
        qtype.save()
        print('Updated quanttype')
        updated_qtype = True
    quanttype_switch_isobaric_update(oldqtype, updated_qtype, data, dset_id)
    if data['labelfree']:
        oldqsf = models.QuantSampleFile.objects.filter(
            rawfile__dataset_id=dset_id)
        oldqsf = {x.rawfile_id: x for x in oldqsf}
        # iterate filenames because that is correct object, 'samples'
        # can contain models that are not active
        for fn in data['filenames']:
            try:
                samplefile = oldqsf.pop(fn['associd'])
            except KeyError:
                models.QuantSampleFile.objects.create(
                    rawfile_id=fn['associd'],
                    projsample_id=data['samples'][str(fn['associd'])]['model'])
            else:
                if data['samples'][str(fn['associd'])]['model'] != samplefile.projsample_id:
                    samplefile.projsample_id = data['samples'][str(fn['associd'])]['model']
                    samplefile.save()
        # delete non-existing qsf (files have been popped)
        [qsf.delete() for qsf in oldqsf.values()]
    dset = models.Dataset.objects.get(pk=dset_id)
    update_admin_defined_params(dset, data, 'sampleprep')
    # update species, TODO sample specific!
    savedspecies = {x.species_id for x in
                    models.DatasetSpecies.objects.filter(dataset_id=dset_id)}
    newspec = {int(x['id']) for x in data['species']}
    models.DatasetSpecies.objects.bulk_create([models.DatasetSpecies(
        dataset_id=dset_id, species_id=spid)
        for spid in newspec.difference(savedspecies)])
    models.DatasetSpecies.objects.filter(
        species_id__in=savedspecies.difference(newspec)).delete()
    set_component_state(dset_id, 'sampleprep', COMPSTATE_OK)
    return JsonResponse({})


@login_required
def save_pooled_lc(request):
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    dset_id = data['dataset_id']
    try:
        qtype = models.QuantDataset.objects.select_related(
            'quanttype').get(dataset_id=dset_id)
    except models.QuantDataset.DoesNotExist:
        # new data, insert, not updating
        models.QuantDataset.objects.create(dataset_id=dset_id, quanttype_id=data['quanttype'])
    else:
        if data['quanttype'] != qtype.quanttype_id:
            qtype.quanttype_id = data['quanttype']
            qtype.save()
    set_component_state(dset_id, 'pooledlabelchecksamples', COMPSTATE_OK)
    return JsonResponse({})


@login_required
def save_labelcheck(request):
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    dset_id = data['dataset_id']
    try:
        qtype = models.QuantDataset.objects.select_related(
            'quanttype').get(dataset_id=dset_id)
    except models.QuantDataset.DoesNotExist:
        # new data, insert, not updating
        models.QuantDataset.objects.create(dataset_id=dset_id, quanttype_id=data['quanttype'])
        models.QuantFileChannelSample.objects.bulk_create([
            models.QuantFileChannelSample(dsrawfile_id=fid, projsample_id=sam['sample'],
                channel_id=sam['channel']) for fid, sam in data['samples'].items()])
    else:
        update_labelcheck(data, qtype)
    set_component_state(dset_id, 'labelchecksamples', COMPSTATE_OK)
    return JsonResponse({})


@login_required
def save_sampleprep(request):
    data = json.loads(request.body.decode('utf-8'))
    user_denied = check_save_permission(data['dataset_id'], request.user)
    if user_denied:
        return user_denied
    dset_id = data['dataset_id']
    try:
        qtype = models.QuantDataset.objects.select_related(
            'quanttype').get(dataset_id=dset_id)
    except models.QuantDataset.DoesNotExist:
        pass  # new data, insert, not updating
    else:
        return update_sampleprep(data, qtype)
    if data['enzymes']:
        models.EnzymeDataset.objects.bulk_create([models.EnzymeDataset(
            dataset_id=dset_id, enzyme_id=x['id']) for x in data['enzymes'] if x['checked']])
    models.QuantDataset.objects.create(dataset_id=dset_id,
                                       quanttype_id=data['quanttype'])
    if not data['labelfree']:
        store_new_channelsamples(data)
    else:
        print('Saving labelfree')
        models.QuantSampleFile.objects.bulk_create([
            models.QuantSampleFile(rawfile_id=fid, projsample_id=data['samples'][str(fid)]['model'])
            for fid in [x['associd'] for x in data['filenames']]])
    save_admin_defined_params(data, dset_id)
    # TODO species to sample specific
    models.DatasetSpecies.objects.bulk_create([models.DatasetSpecies(
        dataset_id=dset_id, species_id=spid['id']) for spid in data['species']])
    set_component_state(dset_id, 'sampleprep', COMPSTATE_OK)
    return JsonResponse({})


def set_component_state(dset_id, compname, state):
    comp = models.DatasetComponentState.objects.get(
        dataset_id=dset_id, dtcomp__component__name=compname)
    comp.state = state
    comp.save()


def update_admin_defined_params(dset, data, category):
    fieldparams = dset.fieldparametervalue_set.filter(
        param__category__labcategory=category)
    selectparams = dset.selectparametervalue_set.filter(
        value__param__category__labcategory=category).select_related('value')
    checkboxparamvals = dset.checkboxparametervalue_set.filter(
        value__param__category__labcategory=category).select_related('value')
    selectparams = {p.value.param_id: p for p in selectparams}
    fieldparams = {p.param_id: p for p in fieldparams}
    checkboxparams = {}
    for p in checkboxparamvals:
        try:
            checkboxparams[p.value.param_id][p.value_id] = p
        except KeyError:
            checkboxparams[p.value.param_id] = {p.value_id: p}
    new_selects, new_fields = [], []
    for param in data['params'].values():
        value = param['model']
        pid = param['param_id']
        if param['inputtype'] == 'select':
            if (pid in selectparams and value != selectparams[pid].value_id):
                selectparams[pid].value_id = value
                selectparams[pid].save()
            elif pid not in selectparams:
                models.SelectParameterValue.objects.create(
                    dataset_id=data['dataset_id'], value_id=value)
        elif param['inputtype'] == 'checkbox':
            value = [box['value'] for box in param['fields'] if box['checked']]
            if pid in checkboxparams:
                oldvals = {val_id: pval for val_id, pval in checkboxparams[pid].items()}
                models.CheckboxParameterValue.objects.bulk_create([
                    models.CheckboxParameterValue(dataset_id=data['dataset_id'],
                                                  value_id=newval)
                    for newval in set(value).difference(oldvals)])
                for removeval in set(oldvals.keys()).difference(value):
                    oldvals[removeval].delete()
            elif pid not in checkboxparams:
                models.CheckboxParameterValue.objects.bulk_create([
                    models.CheckboxParameterValue(
                        dataset_id=data['dataset_id'], value_id=val)
                    for val in value])
        else:
            if pid in fieldparams and value != fieldparams[pid].value:
                fieldparams[pid].value = value
                fieldparams[pid].save()
            elif pid not in fieldparams:
                models.FieldParameterValue.objects.create(
                    dataset_id=data['dataset_id'], param_id=pid, value=value)
    # FIXME delete old ones?


def save_admin_defined_params(data, dset_id):
    selects, checkboxes, fields = [], [], []
    for param in data['params'].values():
        if param['inputtype'] == 'select':
            value = param['model']
            selects.append(models.SelectParameterValue(dataset_id=dset_id,
                                                       value_id=value))
        elif param['inputtype'] == 'checkbox':
            value = [box['value'] for box in param['fields'] if box['checked']]
            checkboxes.extend([models.CheckboxParameterValue(dataset_id=dset_id,
                                                            value_id=val) for val in value])
        else:
            value = param['model']
            fields.append(models.FieldParameterValue(dataset_id=dset_id,
                                                     param_id=param['param_id'],
                                                     value=value))
    models.SelectParameterValue.objects.bulk_create(selects)
    models.CheckboxParameterValue.objects.bulk_create(checkboxes)
    models.FieldParameterValue.objects.bulk_create(fields)
