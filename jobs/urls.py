from django.conf.urls import url
from jobs import views


app_name = 'jobs'
urlpatterns = [
    url(r'^taskfail/$', views.task_failed, name='taskfail'),
    url(r'^retry/(?P<job_id>[0-9]+)$', views.retry_job, name='taskfail'),
    url(r'^set/storagepath/$', views.update_storagepath_file,
        name='updatestorage'),
    url(r'^set/md5/$', views.set_md5, name='setmd5'),
    url(r'^delete/$', views.delete_storedfile,
        name='deletefile'),
    url(r'^set/pxdataset/$', views.downloaded_px_file, name='downloadpx'),
    url(r'^swestore/set/$', views.created_swestore_backup,
        name='createswestore'),
    url(r'^set/mzmlcreate/$', views.created_mzml, name='createmzml'),
    url(r'^set/mzmldone/$', views.scp_mzml, name='scpmzml'),
    url(r'^set/longqc/$', views.store_longitudinal_qc, name='storelongqc'),
    url(r'^set/analysis/$', views.analysis_run_done, name='analysisdone'),
    url(r'^set/analysisfiles/$', views.store_analysis_result, name='analysisfile'),
]
