from django.conf.urls import url
from jobs import views


app_name = 'jobs'
urlpatterns = [
    url(r'^taskfail/$', views.task_failed, name='taskfail'),
    url(r'^retry/$', views.retry_job, name='retry'),
    url(r'^set/storagepath/$', views.update_storagepath_file, name='updatestorage'),
    url(r'^set/md5/$', views.set_md5, name='setmd5'),
    url(r'^unzipped/$', views.unzipped_folder, name='unzipped'),
    url(r'^delete/$', views.delete_job, name='deletejob'),
    url(r'^deletefile/$', views.purge_storedfile, name='deletefile'),
    url(r'^deletedir/$', views.removed_emptydir, name='rmdir'),
    url(r'^set/pxdataset/$', views.downloaded_px_file, name='downloadpx'),
    url(r'^swestore/set/$', views.created_swestore_backup, name='createswestore'),
    url(r'^pdcarchive/set/$', views.created_pdc_archive, name='createpdcarchive'),
    url(r'^pdcrestore/set/$', views.restored_archive_file, name='restoredpdcarchive'),
    url(r'^set/mzmlcreate/$', views.created_mzml, name='createmzml'),
    url(r'^set/mzmldone/$', views.scp_mzml, name='scpmzml'),
    url(r'^set/longqc/$', views.store_longitudinal_qc, name='storelongqc'),
    url(r'^set/analysis/$', views.analysis_run_done, name='analysisdone'),
    url(r'^set/mzmlfile/$', views.mzml_convert_or_refine_file_done, name='mzmlfiledone'),
    url(r'^set/analysisfiles/$', views.store_analysis_result, name='analysisfile'),
]
