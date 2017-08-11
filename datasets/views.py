import json
from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from datasets import models


# Minimal dataset: Only proj, PI, expname
# Can add Files, Metadata whenever
# Typical dataset is one multifraction run
#   so e.g. IPG plate, IP/longgradient samples), or labelcheck
INTERNAL_PI_PK = 1


def home(request):
    return render()


@login_required
def show_dataset(request):
    pass


@login_required
def dataset_project(request, dataset_id):
    response_json = empty_dataset_json()
    if dataset_id:
        print(dataset_id)
        dset = models.Dataset.objects.select_related(
            'project', 'datatype').get(pk=dataset_id)
        response_json.update(dataset_json(dset, dset.project))
    return JsonResponse(response_json)


@login_required
def new_dataset(request):
    """Returns dataset view with form:
        - project/CF (with DB), ask Hillevi
        - PI/internal
          - if external, add extra contact if necessary
        - Exp name (free text)
          - use example names (wt vs mut, NOT pI range or TMT things?,
            But sometimes these are very handy),
        - Files (pick from DB, or if they are not there, input yourself)
       And hidden red forms for sample prep, acquisition, files
    # FIXME datasets can/will be divided in:
    # proj/expname/tmtset/IEF range.
    # thus expname can hold both tmt set names (set1/set2) or hirief range.
    # Bad!

    """
    # Example context, probably make more dynamic
    proj= {
        'expname': '', 'contact': False,
        # FIXME config file or DB (and then have id)
        # FIXME quant type and dataset type require change of input, check
        # it
        # FIXME read up on v-model, there are some implications there
        'hirief_ranges': ['3-10', '3.7-4.9'],
    }
    filecontext = {
        'newdataset': True,
        'unclaimed_files':
        [{'name': 'file1.mzML', 'id': 1, 'instrument': 'qe1', 'date': 'today'},
         {'name': 'file2.mzML', 'id': 2, 'instrument': 'qe1', 'date': 'today'},
         {'name': 'file3.mzML', 'id': 3, 'instrument': 'luke',
          'date': 'yesterday'},
         ],
        'dataset_files': [],
    }
    acquisitioncontext = {
        # FIXME operators from DB
        'operators': [{'name': 'Georgios', 'id': 6}, {'name': 'Rui', 'id': 1},
                      {'name': 'Ghazaleh', 'id': 5}],
    }
    sampleprepcontext = {
        # FIXME most of this should be from config file
        'extract_methods': ['FASP', 'SDS', 'None'],
        'alkylation_methods': ['IAA', 'MMTS', 'None'],
        'enzymes': ['trypsin', 'Lys-C', 'None'],
        'quant_methods': ['TMT11plex', 'TMT10plex', 'TMT6plex', 'TMT2plex',
                          'iTRAQ8plex', 'iTRAQ4plex', 'SILAC', 'labelfree'],

    }
    # FIXME make multiple views, one for each app, json?
    # But then we will not render the template. Shite.
    # FIXME hirief strip in dataset bc there it says hirief in which type of
    # dset it is
    context = {'dataset_id': ''}
    context.update(filecontext)
    context.update(acquisitioncontext)
    context.update(sampleprepcontext)
    return render(request, 'datasets/dataset.html', context)


@login_required
def get_files(request):
    # FIXME return JSON for Vue:w
    pass


@login_required
def save_dataset(request):
    # FIXME this should also be able to update the dataset, and diff against an
    # existing dataset
    # FIXME save hirief range, which ones exist etc? admin task or config.
    data = json.loads(request.body.decode('utf-8'))
    if data['dataset_id']:
        # diff dataset and update necessary fields
        # if a new pi or project is in data, fix that too
        # look in django to see how to hit db least amount of times
        pass
    if data['newprojectname']:
        if data['newpiname']:
            pi = models.PrincipalInvestigator(name=data['newpiname'])
            pi.save()
            project = models.Project(name=data['newprojectname'], pi=pi,
                                     corefac=data['is_corefac'])
        else:
            project = models.Project(name=data['newprojectname'],
                                     pi_id=data['pi_id'],
                                     corefac=data['is_corefac'])
        project.save()
    else:
        project = models.Project.objects.get(pk=data['project_id'])
    dset = models.Dataset(user_id=request.user.id, date=datetime.now(),
                          experiment=data['expname'], project=project,
                          datatype_id=data['datatype_id'])
    dset.save()
    response_json = empty_dataset_json()
    if dset.datatype_id == 1:
        hrds = models.HiriefDataset(dataset=dset,
                                    hirief_id=data['hiriefrange'])
        hrds.save()
        response_json.update(hr_dataset_json(hrds))
    if data['is_corefac']:
        dset_mail = models.CorefacDatasetContact(dataset=dset,
                                                 email=data['corefaccontact'])
        dset_mail.save()
        response_json.update(cf_dataset_json(dset_mail))
    else:
        response_json.update(dataset_json(dset, project))
    return JsonResponse(response_json)


def empty_dataset_json():
    return {'projects': [{'name': x.name, 'id': x.id, 'corefac': x.corefac,
                          'select': False, 'pi_id': x.pi_id} for x in
                         models.Project.objects.all()],
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


def dataset_json(dset, project):
    return {'dataset_id': dset.id,
            'expname': dset.experiment,
            'pi_id': project.pi_id,
            'project_id': project.id,
            'is_corefac': project.corefac,
            'datatype_id': dset.datatype_id,
            }


def cf_dataset_json(dset_mail):
    return {'externalcontactmail': dset_mail.email}


def hr_dataset_json(hirief_ds):
    return {'hiriefrange': hirief_ds.hirief_id}


@login_required
def save_dataset_files(request):
    pass


@login_required
def save_dataset_acquisition(request):
    pass


@login_required
def save_dataset_sampleprep(request):
    pass


@login_required
def save_project(request):
    pass


@login_required
def save_masspec(request):
    pass


@login_required
def save_sampleprep(request):
    pass


@login_required
def save_files(request):
    pass
