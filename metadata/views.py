from django.http import HttpResponse
from django.shortcuts import render_to_response, render, redirect
import copy, os, tempfile, json
import configurefields

ps = configurefields.ParameterSet()

# should prob be in util module
def get_uploaded_files():
    return sorted(os.listdir('/mnt/kalevalatmp'))
    
def newmetadata(request):
    return render(request, 'metadata/metadata_input.html', {'param_set': ps})


def login_page(request):
    return HttpResponse('login page')


def new_dataset(request):
    if request.method == 'POST':
        print request.POST
        if request.POST['step'] == 'file_input':
            # files come in, now write metadata
            if not request.POST['pastefiles'] and \
                'selectfiles' not in request.POST:
                return render(request, 'metadata/file_input.html', 
                    {'filelist': get_uploaded_files() })
            else:
                filelist = request.POST['pastefiles']
                if filelist == '':
                    filelist = []
                else:
                    filelist = [x.strip() for x in filelist.strip().split('\n')]
                if 'selectfiles' in request.POST:
                    filelist.extend(request.POST.getlist('selectfiles'))
                print filelist

                ps.tmpdir = tempfile.mkdtemp(dir='tmp')
                with open(os.path.join(ps.tmpdir, 'filelist.json'), 'w') as fp:
                    json.dump(filelist, fp)
                return render(request, 'metadata/metadata_input.html',
                    {'param_set': ps})

        elif request.POST['step'] in ['base_meta_input', 'outlier_meta']:
            loaded_ps = copy.deepcopy(ps)
            loaded_ps.incoming_metadata(request.POST)

            if loaded_ps.error:
                if not loaded_ps.is_outlier:
                    loaded_ps.add_outliers = False
                else:
                    loaded_ps.add_outliers = True
                return render(request, 'metadata/metadata_input.html', {'param_set': loaded_ps})
            else:
                loaded_ps.autodetection()
                loaded_ps.save_tmp_parameters()
                
                if loaded_ps.add_outliers:
                    return render(request, 'metadata/metadata_input.html',
                        {'param_set': loaded_ps})
                else:
                    return store_dataset(request, loaded_ps)
                            
    else:
        return render(request, 'metadata/file_input.html', 
            {'filelist': get_uploaded_files()})


def store_dataset(request, loaded_ps=None):
    if request.method == 'POST':
        if request.POST['step'] in ['base_meta_input', 'outlier_meta']:
            loaded_ps.gather_metadata()
            return render(request, 'metadata/store_dataset.html', {'param_set': loaded_ps})
        else:
            loaded_ps.push_definite_metadata()
            return render(request, 'metadata/succesful_storage.html', {'param_set': loaded_ps})

    else:
        return redirect('/kantele/newdataset')

