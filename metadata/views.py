from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from models import Dataset, DraftDataset
from db import dbaccess
import copy
import metadata 

empty_mds = metadata.MetadataSet()

@login_required
def new_dataset(request):
    mds = deepcopy_metadataset(empty_mds)
    oid = mds.new_dataset(request)
    return redirect('/kantele/dataset/files/{0}'.format(oid))

@login_required
def edit_dataset(request, dataset_id):
    mds = deepcopy_metadataset(empty_mds)
    mds.edit_dataset(request, dataset_id)
    return redirect('/kantele/dataset/{0}'.format(dataset_id))


@login_required
def copy_dataset(request, dataset_id):
    mds = deepcopy_metadataset(empty_mds)
    oid = mds.copy_dataset(request, dataset_id)
    return redirect('/kantele/dataset/files/{0}'.format(oid))

@login_required
def show_dataset(request, dataset_id):
    if request.method == 'GET':
        return dataset_view_action(request, dataset_id, 'base_meta.html')
    else:
        return redirect('/kantele')

@login_required
def select_files(request, dataset_id):    
    return dataset_view_action(request, dataset_id, 'file_input.html', 'metadata')

@login_required
def write_metadata(request, dataset_id):
    return dataset_view_action(request, dataset_id, 'base_meta.html', 'outliers')

@login_required
def define_outliers(request, dataset_id):
    return dataset_view_action(request, dataset_id, 'outliers.html', 'store')

@login_required
def store_dataset(request, dataset_id):
    if request.method == 'GET':
        # or should we redirect to kantele when get comes?
        return dataset_view_action(request, dataset_id, 'store.html')
    elif request.method == 'POST':
        mds = check_dataset_owner(request, dataset_id)
        if not mds:
            return redirect('/kantele')
        else:
            mds.store_dataset(request, dataset_id) 
            return redirect('/kantele') # Can we add a message: congratulations here?


def dataset_view_action(request, dataset_id, template, nextstep=None):
    def return_get(request, template, ds_id, mds, message=None):
        return render(request, 'metadata/{0}'.format(template), {'mds': mds,
                'ds_id': ds_id, 'message': message} )

    mds = check_dataset_owner(request, dataset_id)
    if not mds:
        return redirect('/kantele')
        
    elif request.method == 'POST':
        mds.incoming_form(request, dataset_id)
        if mds.error:
            if mds.error['redirect'] == 'return_to_form':
                mds.show_errored_dataset(request, dataset_id)
                return return_get(request, template, dataset_id, mds,
                        message=mds.error['message'])
            elif mds.error['redirect'] == 'home':
                return redirect('home', message=mds.error['message'])

        # when editing: redirect to dataset view, when creating new: next step
        if request.session.get('metadatastatus', None) == 'new':
            # there is a button for more outliers
            if template == 'outliers.html' and mds.more_outliers == True:
                nextstep = 'outliers'
            return redirect('/kantele/dataset/{0}/{1}'.format(nextstep,
                    dataset_id)) 
        else:
            return redirect('/kantele/dataset/{0}'.format(mds.obj_id)) 

    elif request.method == 'GET':
        mds.show_dataset(request, dataset_id)
        return return_get(request, template, dataset_id, mds)
    
def deepcopy_metadataset(mds):
    """Database access cannot be deepcopied since it contains mongo
    collections"""
    new_mds = copy.deepcopy(mds)
    new_mds.db = dbaccess.DatabaseAccess()
    return new_mds

def check_dataset_owner(request, dataset_id):
    if request.method not in ['POST', 'GET']:
        return False
    elif dataset_id in \
            [x.mongoid for x in Dataset.objects.filter(user=request.user.pk)]:
        return deepcopy_metadataset(empty_mds)
    elif dataset_id in \
            [x.mongoid for x in DraftDataset.objects.filter(user=request.user.pk)]:
        return deepcopy_metadataset(empty_mds)
    else:
        return False
