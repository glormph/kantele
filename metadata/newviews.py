from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from models import Dataset
import copy
import metadata 

empty_mds = metadata.MetadataSet()


@login_required
def new_dataset(request):
    mds = copy.deepcopy(empty_mds)
    oid = mds.initialize_new_dataset()
    # FIXME store oid also in sql
    redirect('/kantele/files/{0}'.format(str(oid)) )

@login_required
def edit_dataset(request, dataset_id):
    mds = copy.deepcopy(empty_mds)
    mds.load_from_db(dataset_id)
    mds.update_db_status('tmp')
    mds.create_draft_from_metadata()
    redirect('/kantele/dataset/{0}'.format(dataset_id))
    

@login_required
def show_dataset(request, dataset_id):
    if request.method == 'GET':
        dataset_view_action(request, dataset_id, 'show_dataset.html')
    else:
        redirect('/kantele')


@login_required
def add_files(request, dataset_id):    
    dataset_view_action(request, dataset_id, 'file_input.html', 'metadata')


@login_required
def write_metadata(request, dataset_id):
    dataset_view_action(request, dataset_id, 'base_meta.html', 'outliers')


@login_required
def define_outliers(request, dataset_id):
    dataset_view_action(request, dataset_id, 'outliers.html', 'store')


@login_required
def store_dataset(request, dataset_id):
    dataset_view_action(request, dataset_id, 'store.html', 'succesful_storage.html')


def dataset_view_action(request, dataset_id, template, nextstep=None):
    mds = copy.deepcopy(empty_mds)
    if dataset_id not in \
            [x.mongoid for x in Dataset.objects.filter(user=request.user.pk)] or \
            request.method not in ['POST', 'GET']:
        return redirect('/kantele')
        
    elif request.method == 'POST':
        mds.incoming_form(request.POST, dataset_id)
        # FIXME check for problems in mds:
        
        # when editing: redirect to dataset view, when creating new: next step
        if mds.status == 'creating':
            return redirect('/kantele/dataset/{0}/{1}'.format(nextstep, mds.obj_id)) 
        else:
            return redirect('/kantele/dataset/{0}'.format(mds.obj_id)) 

    elif request.method == 'GET':
        mds.load_from_db(request.user, dataset_id)
        return render(request, 'metadata/{0}'.format(template), {'mds': mds} )
    

def test(request, dataset_id):
    print [x.mongoid for x in Dataset.objects.filter(user=request.user.pk) ]
    return redirect('/kantele')    

