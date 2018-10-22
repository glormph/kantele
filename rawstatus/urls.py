from django.conf.urls import url
from rawstatus import views


app_name = 'files'
urlpatterns = [
    url(r'^$', views.show_files, name='latestfiles'),
    url(r'^register/$', views.register_file, name='register'),
    url(r'^register/userfile/$', views.register_userupload, name='registeruserupload'),
    url(r'^userfile/$', views.request_userupload, name='req_userupload'),
    url(r'^upload/userfile/$', views.upload_userfile, name='upload_userfile'),
    url(r'^transferred/$', views.file_transferred, name='transferred'),
    url(r'^md5/$', views.check_md5_success, name='md5check'),
    url(r'^md5/userfile/$', views.check_md5_success_userfile, name='md5checkuserfile'),
    url(r'^setlibrary/$', views.set_libraryfile),
    url(r'^libfile/$', views.check_libraryfile_ready),
]
