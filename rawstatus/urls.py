from django.conf.urls import url
from rawstatus import views


app_name = 'files'
urlpatterns = [
    url(r'^$', views.show_files, name='latestfiles'),
    url(r'^register/$', views.register_file, name='register'),
    url(r'^transferred/$', views.file_transferred, name='transferred'),
    url(r'^md5/$', views.check_md5_success, name='md5check'),
    url(r'^setlibrary/$', views.set_libraryfile),
    url(r'^libfile/$', views.check_libraryfile_ready),
]
