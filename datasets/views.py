import json
from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse

from datasets import models
from rawstatus import models as filemodels


INTERNAL_PI_PK = 1


def home(request):
    return render()



@login_required
def new_dataset(request):
    """Returns dataset view with Vue apps that will separately request
    forms"""
    context = {'dataset_id': '', 'newdataset': True}
    return render(request, 'datasets/dataset.html', context)


@login_required
def show_dataset(request, dataset_id):
    context = {'dataset_id': dataset_id, 'newdataset': False}
    return render(request, 'datasets/dataset.html', context)


@login_required
def dataset_project(request, dataset_id):
    response_json = empty_dataset_proj_json()
    if dataset_id:
        dset = models.Dataset.objects.select_related(
            'experiment__project', 'datatype',
            'hiriefdataset').get(pk=dataset_id)
        response_json.update(dataset_proj_json(dset, dset.experiment.project))
        if hasattr(dset, 'hiriefdataset'):
            response_json.update(hr_dataset_proj_json(dset.hiriefdataset))
        if dset.experiment.project.corefac:
            mail = models.CorefacDatasetContact.objects.get(dataset_id=dset.id)
            response_json.update(cf_dataset_proj_json(mail))
    return JsonResponse(response_json)


@login_required
def dataset_files(request, dataset_id):
    response_json = empty_files_json()
    if dataset_id:
        response_json.update(
            {'datasetAssociatedFiles':
             {'id_{}'.format(x.rawfile_id):
              {'id': x.rawfile_id, 'name': x.rawfile.name,
               'instrument': x.rawfile.producer.name, 'date': x.rawfile.date}
              for x in models.DatasetRawFile.objects.select_related(
                  'rawfile__producer').filter(dataset_id=dataset_id)}})
    return JsonResponse(response_json)


@login_required
def dataset_acquisition(request, dataset_id):
    response_json = empty_acquisition_json()
    if dataset_id:
        try:
            response_json.update({'operator_id':
                                  models.OperatorDataset.objects.get(
                                      dataset_id=dataset_id).operator_id})
        except models.OperatorDataset.DoesNotExist:
            return JsonResponse(response_json)
        get_admin_params_for_dset(response_json, dataset_id, 'acquisition')
    response_json['params'] = [x for x in response_json['params'].values()]
    return JsonResponse(response_json)


@login_required
def dataset_sampleprep(request, dataset_id):
    response_json = empty_sampleprep_json()
    if dataset_id:
        response_json['enzymes'] = [
            x.enzyme.id for x in models.EnzymeDataset.objects.filter(
                dataset_id=dataset_id).select_related('enzyme')]
        if not response_json['enzymes']:
            response_json['no_enzyme'] = True
        # quanttype FIXME
        #qtype = models.QuantDataset.objects.get(dataset_id=dataset_id).quanttype_id
        #QuantChannelSample.objects.filter(dataset_id=dataset_id).select_related(
        get_admin_params_for_dset(response_json, dataset_id, 'sampleprep')
    response_json['params'] = [x for x in response_json['params'].values()]
    return JsonResponse(response_json)


def get_admin_params_for_dset(params, dset_id, category):
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
            fill_admin_selectparam(oldparams, p.value, p.value.id, p.title)
    for p in models.FieldParameterValue.objects.filter(
            dataset_id=dset_id,
            param__category__labcategory=category).select_related(
            'param__category'):
        params_saved = True
        if p.param.active:
            fill_admin_fieldparam(params, p.param, p.value)
        else:
            fill_admin_fieldparam(oldparams, p.param, p.value, p.title)
    if not params_saved:
        # not saved for this dset id so dont return the params
        return
    # Parse new params, old params
    # use list comprehension so no error: dict changes during iteration
    for p_id in [x for x in params.keys()]:
        if params[p_id]['model'] == '':
            newparams[p_id] = params.pop(p_id)
    if params_saved:
        response['oldparams'] = [x for x in oldparams.values()]
        response['newparams'] = [x for x in newparams.values()]


@login_required
def get_files(request):
    # FIXME return JSON for Vue:w
    pass


def update_dataset(data):
    # FIXME this needs to also change file location
    dset = models.Dataset.objects.select_related().get(pk=data['dataset_id'])
    oldexp, oldproj = dset.experiment_id, dset.experiment.project_id
    if 'newprojectname' in data:
        project = newproject_save(data)
        project_id = project.id
    else:
        project_id = data['project_id']
    if 'newexperimentname' in data:
        experiment = models.Experiment(name=data['newexperimentname'],
                                       project_id=project_id)
        experiment.save()
        exp_id = experiment.id
    else:
        exp_id = data['experiment_id']
    dset.experiment_id = exp_id
    # update hirief, including remove hirief range binding if no longer hirief
    hrf_id = models.Datatype.objects.get(name__icontains='hirief')
    if dset.datatype_id == hrf_id and dset.datatype_id != data['datatype_id']:
        models.HiriefDataset.objects.get(
            dataset_id=data['dataset_id']).delete()
    elif data['datatype_id'] == hrf_id:
        if dset.hiriefdataset.hirief_id != data['hiriefrange']:
            dset.hiriefdataset.hirief_id = data['hiriefrange']
            dset.hiriefdataset.save()
    dset.datatype_id = data['datatype_id']
    dset.save()
    if data['is_corefac']:
        if dset.corefacdatasetcontact.email != data['corefaccontact']:
            dset.corefacdatasetcontact.email = data['corefaccontact']
            dset.corefacdatasetcontact.save()
    # FIXME delete old project if no experiment? Or only admin?
    # FIXME delete old experiment if no datasets ?
    return HttpResponse()


def newproject_save(data):
    if 'newpiname' in data:
        pi = models.PrincipalInvestigator(name=data['newpiname'])
        pi.save()
        project = models.Project(name=data['newprojectname'], pi=pi,
                                 corefac=data['is_corefac'])
    else:
        project = models.Project(name=data['newprojectname'],
                                 pi_id=data['pi_id'],
                                 corefac=data['is_corefac'])
    project.save()
    return project


@login_required
def save_dataset(request):
    # FIXME this should also be able to update the dataset, and diff against an
    # existing dataset
    data = json.loads(request.body.decode('utf-8'))
    if data['dataset_id']:
        print('Updating')
        return update_dataset(data)
    if 'newprojectname' in data:
        project = newproject_save(data)
    else:
        project = models.Project.objects.get(pk=data['project_id'])
    if 'newexperimentname' in data:
        experiment = models.Experiment(name=data['newexperimentname'],
                                       project_id=project.id)
        experiment.save()
        exp_id = experiment.id
    else:
        exp_id = data['experiment_id']
    dset = models.Dataset(user_id=request.user.id, date=datetime.now(),
                          experiment_id=exp_id,
                          datatype_id=data['datatype_id'])
    dset.save()
    if dset.datatype_id == 1:
        hrds = models.HiriefDataset(dataset=dset,
                                    hirief_id=data['hiriefrange'])
        hrds.save()
    if data['is_corefac']:
        dset_mail = models.CorefacDatasetContact(dataset=dset,
                                                 email=data['corefaccontact'])
        dset_mail.save()
    return HttpResponse()


def empty_dataset_proj_json():
    projects = [{'name': x.name, 'id': x.id, 'corefac': x.corefac,
                 'select': False, 'pi_id': x.pi_id} for x in
                models.Project.objects.all()]
    experiments = {x['id']: [] for x in projects}
    for exp in models.Experiment.objects.select_related('project').all():
        experiments[exp.project.id].append({'id': exp.id, 'name': exp.name})
    return {'projects': projects, 'experiments': experiments,
            'external_pis': [{'name': x.name, 'id': x.id} for x in
                             models.PrincipalInvestigator.objects.all()],
            'datatypes': [{'name': x.name, 'id': x.id} for x in
                          models.Datatype.objects.all()],
            'internal_pi_id': INTERNAL_PI_PK,
            'datasettypes': [{'name': x.name, 'id': x.id} for x in
                             models.Datatype.objects.all()],
            'hirief_ranges': [{'name': str(x), 'id': x.id}
                              for x in models.HiriefRange.objects.all()]
            }


def dataset_proj_json(dset, project):
    return {'dataset_id': dset.id,
            'experiment_id': dset.experiment_id,
            'pi_id': project.pi_id,
            'project_id': project.id,
            'existingproject_iscf': project.corefac,
            'datatype_id': dset.datatype_id,
            }


def cf_dataset_proj_json(dset_mail):
    return {'externalcontactmail': dset_mail.email}


def hr_dataset_proj_json(hirief_ds):
    return {'hiriefrange': hirief_ds.hirief_id}


def empty_sampleprep_json():
    params = get_dynamic_emptyparams('sampleprep')
    quants = {}
    for chan in models.QuantTypeChannel.objects.all().select_related(
            'quanttype', 'channel'):
        if not chan.quanttype.id in quants:
            quants[chan.quanttype.id] = {'id': chan.quanttype.id, 'chans': [],
                                         'name': chan.quanttype.name}
        quants[chan.quanttype.id]['chans'].append({'id': chan.channel.id,
                                                   'name': chan.channel.name,
                                                   'model': ''})
    labelfree = models.QuantType.objects.get(name='labelfree')
    quants[labelfree.id] = {'id': labelfree.id, 'name': 'labelfree',
                            'model': ''}
    return {'params': params, 'quants': quants,
            'show_enzymes': [{'id': x.id, 'name': x.name}
                             for x in models.Enzyme.objects.all()]}


def fill_admin_selectparam(params, p, value=False, oldparamtitle=False):
    """Fills params dict with select parameters passed, in proper JSON format
    for Vue app.
    This takes care of both empty params (for new dataset), filled parameters,
    and old parameters"""
    if not p.param.id in params:
        params[p.param.id] = {'param_id': p.param.id, 'fields': [],
                              'inputtype': 'select'}
    params[p.param.id]['title'] = (oldparamtitle if oldparamtitle
                                   else p.param.title)
    if value:
        # fields is already populated
        params[p.param.id]['model'] = value
    else:
        params[p.param.id]['model'] = ''
        params[p.param.id]['fields'].append({'value': p.id, 'text': p.value})


def fill_admin_fieldparam(params, p, value=False, oldparamtitle=False):
    """Fills params dict with field parameters passed, in proper JSON format
    for Vue app.
    This takes care of both empty params (for new dataset), filled parameters,
    and old parameters"""
    params[p.id] = {'id': p.id, 'placeholder': p.placeholder,
                    'inputtype': p.paramtype.typename}
    params[p.id]['title'] = oldparamtitle if oldparamtitle else p.title
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
    return params


def empty_acquisition_json():
    params = get_dynamic_emptyparams('acquisition')
    return {'params': params,
            'operators': [{'id': x.user.id, 'name': '{} {}'.format(
                x.user.first_name, x.user.last_name)}
                for x in models.Operator.objects.select_related('user').all()]}


def dataset_files_json(dset):
    pass


def empty_files_json():
    return {'newFiles': {'id_{}'.format(x.id):
                         {'id': x.id, 'name': x.name, 'date': x.date,
                          'instrument': x.producer.name, 'checked': False}
                         for x in filemodels.RawFile.objects.select_related(
                             'producer').filter(claimed=False)}}


@login_required
def save_files(request):
    data = json.loads(request.body.decode('utf-8'))
    dset_id = data['dataset_id']
    added_fnids = [x['id'] for x in data['added_files'].values()]
    models.DatasetRawFile.objects.bulk_create([
        models.DatasetRawFile(dataset_id=dset_id, rawfile_id=fnid) for fnid in
        added_fnids])
    filemodels.RawFile.objects.filter(pk__in=added_fnids).update(claimed=True)
    removed_ids = [int(x['id']) for x in data['removed_files'].values()]
    if removed_ids:
        models.DatasetRawFile.objects.filter(
            dataset_id=dset_id, rawfile_id__in=removed_ids).delete()
        filemodels.RawFile.objects.filter(pk__in=removed_ids).update(
            claimed=False)
    return HttpResponse()


def update_acquisition(dset, data):
    if data['operator_id'] != dset.operatordataset.operator_id:
        dset.operatordataset.operator_id = data['operator_id']
        dset.operatordataset.save()
    update_admin_defined_params(dset, data, 'acquisition')
    return HttpResponse()


@login_required
def save_acquisition(request):
    data = json.loads(request.body.decode('utf-8'))
    dset_id = data['dataset_id']
    dset = models.Dataset.objects.select_related('operatordataset').get(
        pk=data['dataset_id'])
    if hasattr(dset, 'operatordataset'):
        return update_acquisition(dset, data)
    models.OperatorDataset.objects.create(dataset_id=dset_id,
                                          operator_id=data['operator_id'])
    save_admin_defined_params(data, dset_id)
    return HttpResponse()


@login_required
def save_sampleprep(request):
    data = json.loads(request.body.decode('utf-8'))
    dset_id = data['dataset_id']
    if data['enzymes']:
        models.EnzymeDataset.objects.bulk_create([models.EnzymeDataset(
            dataset_id=dset_id, enzyme_id=x) for x in data['enzymes']])
    models.QuantDataset.objects.create(dataset_id=dset_id,
                                       quanttype_id=data['quanttype'])
    if not data['labelfree']:
        models.QuantChannelSample.objects.bulk_create([
            models.QuantChannelSample(dataset_id=dset_id, sample=chan['model'],
                                      channel_id=chan['id'])
            for chan in data['samples']])
    else:
        if not data['multisample']:
            data['samples'] = {}
            for fn in data['filenames']:
                data['samples'][fn['id']] = data['sample']
        models.QuantSampleFile.objects.bulk_create([
            models.QuantSampleFile(dataset_id=dset_id, rawfile_id=file_id,
                                   sample=sample)
            for file_id, sample in data['samples'].items()])
    save_admin_defined_params(data, dset_id)
    return HttpResponse()


def update_admin_defined_params(dset, data, category):
    fieldparams = dset.fieldparametervalue_set.filter(
        param__category__labcategory=category)
    selectparams = dset.selectparametervalue_set.filter(
        value__param__category__labcategory=category).select_related('value')
    selectparams = {p.value.param_id: p for p in selectparams}
    fieldparams = {p.param_id: p for p in fieldparams}
    new_selects, new_fields = [], []
    for param in data['params']:
        value = param['model']
        if param['inputtype'] == 'select':
            pid = param['param_id']
            if (pid in selectparams and value != selectparams[pid].value_id):
                text = [x['text'] for x in param['fields']
                        if x['value'] == value]
                selectparams[pid].value_id = value
                selectparams[pid].valuename = text[0]
                selectparams[pid].save()
            elif pid not in selectparams:
                models.SelectParameterValue.objects.create(
                    dataset_id=data['dataset_id'], value_id=value,
                    valuename=text[0], title=param['title'])
        else:
            pid = param['id']
            if pid in fieldparams and value != fieldparams[pid].value:
                fieldparams[pid].value = value
                fieldparams[pid].save()
            elif pid not in fieldparams:
                models.FieldParameterValue.objects.create(
                    dataset_id=data['dataset_id'], param_id=pid, value=value,
                    title=param['title'])
    # FIXME delete old ones?


def save_admin_defined_params(data, dset_id):
    selects, fields = [], []
    for param in data['params'].values():
        value = param['model']
        if param['inputtype'] == 'select':
            text = [x['text'] for x in param['fields']
                    if x['value'] == value]
            selects.append(models.SelectParameterValue(dataset_id=dset_id,
                                                       value_id=value,
                                                       valuename=text[0],
                                                       title=param['title']))
        else:
            fields.append(models.FieldParameterValue(dataset_id=dset_id,
                                                     param_id=param['id'],
                                                     value=value,
                                                     title=param['title']))
    models.SelectParameterValue.objects.bulk_create(selects)
    models.FieldParameterValue.objects.bulk_create(fields)
