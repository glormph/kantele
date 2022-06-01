from django.conf.urls import url
from jobs import views


app_name = 'jobs'
urlpatterns = [
    url(r'^taskfail/$', views.task_failed, name='taskfail'),
    url(r'^retry/$', views.retry_job, name='retry'),
    url(r'^set/storagepath/$', views.update_storagepath_file, name='updatestorage'),
    url(r'^set/dsstoragepath/$', views.update_storage_loc_dset, name='update_ds_storage'),
    url(r'^set/projectname/$', views.renamed_project, name='renameproject'),
    url(r'^set/md5/$', views.set_md5, name='setmd5'),
    url(r'^unzipped/$', views.unzipped_folder, name='unzipped'),
    url(r'^delete/$', views.delete_job, name='deletejob'),
    url(r'^pause/$', views.pause_job, name='pausejob'),
    url(r'^resume/$', views.resume_job, name='resumejob'),
    url(r'^deletefile/$', views.purge_storedfile, name='deletefile'),
    url(r'^deletedir/$', views.removed_emptydir, name='rmdir'),
    url(r'^set/external/$', views.register_external_file, name='register_external'),
    url(r'^swestore/set/$', views.created_swestore_backup, name='createswestore'),
    url(r'^pdcarchive/set/$', views.created_pdc_archive, name='createpdcarchive'),
    url(r'^pdcrestore/set/$', views.restored_archive_file, name='restoredpdcarchive'),
    # deprecate when stopped using, this is from old pwiz windows
    url(r'^set/mzmlcreate/$', views.created_mzml, name='createmzml'),
    url(r'^set/mzmldone/$', views.scp_mzml, name='scpmzml'),
    url(r'^set/longqc/$', views.store_longitudinal_qc, name='storelongqc'),
    url(r'^set/analysis/$', views.analysis_run_done, name='analysisdone'),
    url(r'^set/mzmlfile/$', views.mzml_convert_or_refine_file_done, name='mzmlfiledone'),
    url(r'^set/analysisfiles/$', views.store_analysis_result, name='analysisfile'),
]
