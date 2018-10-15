from django.conf.urls import url
from home import views

app_name = 'home'
urlpatterns = [
    url(r'^$', views.home, name="home"),
    url(r'^show/datasets/$', views.show_datasets, name="showdatasets"),
    url(r'^show/analyses/$', views.show_analyses, name="showanalyses"),
    url(r'^show/jobs/$', views.show_jobs, name="showjobs"),
    url(r'^show/files/$', views.show_files, name="showfiles"),
    url(r'^find/datasets/$', views.find_datasets, name="finddatasets"),
    url(r'^find/analyses/$', views.find_analysis, name="findanalyses"),
    url(r'^find/files/$', views.find_files, name="findfiles"),
    url(r'^show/dataset/(?P<dataset_id>[0-9]+)$', views.get_dset_info, name="dsinfo"),
    url(r'^show/analysis/(?P<nfs_id>[0-9]+)$', views.get_analysis_info, name="anainfo"),
    url(r'^show/job/(?P<job_id>[0-9]+)$', views.get_job_info, name="jobinfo"),
    url(r'^refresh/job/(?P<job_id>[0-9]+)$', views.refresh_job, name="jobrefresh"),
    url(r'^createmzml/(?P<dataset_id>[0-9]+)$', views.create_mzmls),
    url(r'^refinemzml/(?P<dataset_id>[0-9]+)$', views.refine_mzmls),
]
