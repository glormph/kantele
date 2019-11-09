from django.conf.urls import url
from datasets import views

app_name = 'datasets'
urlpatterns = [
    url(r'^new/$', views.new_dataset, name="new"),
    url(r'^show/(?P<dataset_id>[0-9]+)$', views.show_dataset, name="show"),
    url(r'^show/info/(?P<dataset_id>[0-9]*)$', views.dataset_info),
    url(r'^show/project/(?P<project_id>[0-9]*)$', views.get_project),
    url(r'^show/files/(?P<dataset_id>[0-9]*)$', views.dataset_files,
        name="showfiles"),
    url(r'^find/files/$', views.find_files),
    url(r'^show/sampleprep/(?P<dataset_id>[0-9]*)$', views.dataset_sampleprep,
        name="showprep"),
    url(r'^show/labelcheck/(?P<dataset_id>[0-9]*)$', views.labelcheck_samples),
    url(r'^show/acquisition/(?P<dataset_id>[0-9]*)$',
        views.dataset_acquisition, name="showacquisition"),
    url(r'^show/components/(?P<datatype_id>[0-9]*)$', views.get_datatype_components),
    url(r'^show/species/$', views.get_species),
    url(r'^save/project/$', views.save_dataset, name="saveproject"),
    url(r'^save/files/$', views.save_files, name="savefiles"),
    url(r'^save/acquisition/$', views.save_acquisition, name="saveacqui"),
    url(r'^save/sampleprep/$', views.save_sampleprep, name="saveprep"),
    url(r'^save/labelcheck/$', views.save_labelcheck),
    url(r'^save/owner/$', views.change_owners, name="changeowner"),
    url(r'^save/projsample/$', views.save_projsample),
    url(r'^delete/$', views.set_deleted_dataset),
]
