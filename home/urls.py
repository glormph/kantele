from django.conf.urls import url
from home import views

app_name = 'home'
urlpatterns = [
    url(r'^$', views.home, name="home"),
    url(r'^show/datasets/$', views.show_datasets, name="showdatasets"),
    url(r'^find/datasets/$', views.find_datasets, name="showdatasets"),
    url(r'^show/dataset/(?P<dataset_id>[0-9]+)$', views.get_dset_info, name="info"),
    url(r'^createmzml/(?P<dataset_id>[0-9]+)$', views.create_mzmls),
]
