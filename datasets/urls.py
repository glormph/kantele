from django.conf.urls import url
from datasets import views

app_name = 'datasets'
urlpatterns = [
    url(r'^new/$', views.new_dataset, name="new"),
    url(r'^show/(?P<dataset_id>[0-9]+)$', views.show_dataset, name="show"),
    url(r'^show/project/(?P<dataset_id>[0-9]*)$', views.dataset_project,
        name="showproject"),
    url(r'^show/files/(?P<dataset_id>[0-9]*)$', views.dataset_files,
        name="showfiles"),
    url(r'^show/sampleprep/(?P<dataset_id>[0-9]*)$', views.dataset_sampleprep,
        name="showprep"),
    url(r'^show/acquisition/(?P<dataset_id>[0-9]*)$',
        views.dataset_acquisition, name="showacquisition"),
    url(r'^save/project/$', views.save_dataset, name="saveproject"),
    url(r'^save/files/$', views.save_files, name="savefiles"),
    url(r'^save/acquisition/$', views.save_acquisition, name="saveacqui"),
    url(r'^save/sampleprep/$', views.save_sampleprep, name="saveprep"),
    url(r'^$', views.home, name="home"),
]
