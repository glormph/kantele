from django.conf.urls import url
from datasets import views

app_name = 'datasets'
urlpatterns = [
    url(r'^new/$', views.new_dataset, name="new"),
    url(r'^show/(?P<dataset_id>[0-9]+)$', views.show_dataset, name="show"),
    url(r'^show/project/(?P<dataset_id>[0-9]*)$', views.dataset_project,
        name="showproject"),
    url(r'^save/project/$', views.save_dataset, name="saveproject"),
    url(r'^save/files/$', views.save_dataset, name="savefiles"),
    url(r'^save/acquistion/$', views.save_dataset, name="saveacquisition"),
    url(r'^save/prep/$', views.save_dataset, name="saveprep"),
    url(r'^$', views.home, name="home"),
]
