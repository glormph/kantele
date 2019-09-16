from django.conf.urls import url
from analysis import views


app_name = 'analysis'
urlpatterns = [
    url(r'^init/$', views.get_analysis_init),
    url(r'^run/$', views.start_analysis),
    url(r'^delete/$', views.delete_analysis),
    url(r'^purge/$', views.purge_analysis),
    url(r'^dsets/$', views.get_datasets),
    url(r'^workflow/$', views.get_workflow),
    url(r'^allworkflows/$', views.get_allwfs),
    url(r'^logappend/$', views.append_analysis_log, name='appendlog'),
    url(r'^log/(?P<nfs_id>[0-9]+)$', views.show_analysis_log),
    url(r'^showfile/(?P<file_id>[0-9]+)$', views.serve_analysis_file),
    url(r'^fastarelease/check/$', views.check_fasta_release, name='checkfastarelease'),
]
