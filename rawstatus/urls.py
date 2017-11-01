from django.conf.urls import url
from rawstatus import views


app_name = 'files'
urlpatterns = [
    url(r'^$', views.show_files, name='latestfiles'),
    url(r'^register/$', views.register_file),
    url(r'^transferred/$', views.file_transferred),
    url(r'^md5/set/$', views.set_md5, name='rawstatus-setmd5'),
    url(r'^md5/$', views.check_md5_success),
    url(r'^swestore/set/$', views.created_swestore_backup,
        name='rawstatus-createswestore'),
    url(r'^storagepath/$', views.update_storagepath_file,
        name='rawstatus-updatestorage'),
    url(r'^delete/$', views.delete_storedfile,
        name='rawstatus-deletefile'),
]
