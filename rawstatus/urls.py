from django.conf.urls import url
from rawstatus import views


app_name = 'files'
urlpatterns = [
    url(r'^$', views.show_files, name='latestfiles'),
    url(r'^register/$', views.register_file),
    url(r'^transferred/$', views.file_transferred),
    url(r'^md5/$', views.check_md5_success),
    url(r'^setlibrary/$', views.set_libraryfile),
]
