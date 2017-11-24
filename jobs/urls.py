from django.conf.urls import url
from jobs import views


app_name = 'jobs'
urlpatterns = [
    url(r'^taskfail/$', views.task_failed, name='taskfail'),
    url(r'^set/storagepath/$', views.update_storagepath_file,
        name='updatestorage'),
    url(r'^set/md5/$', views.set_md5, name='setmd5'),
    url(r'^delete/$', views.delete_storedfile,
        name='deletefile'),
    url(r'^swestore/set/$', views.created_swestore_backup,
        name='createswestore'),
    url(r'^set/mzml/$', views.created_mzml, name='createmzml'),
]
