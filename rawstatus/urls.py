from django.conf.urls import url
from rawstatus import views


app_name = 'files'
urlpatterns = [
    url(r'^$', views.show_files, name='latestfiles'),
    url(r'^instruments/$', views.instrument_page, name='instruments'),
    url(r'^instruments/download/$', views.download_instrument_package),
    url(r'^register/$', views.register_file, name='register'),
    url(r'^register/userfile/$', views.register_userupload, name='registeruserupload'),
    url(r'^userfile/$', views.request_token_userupload, name='req_userupload'),
    url(r'^upload/token/$', views.upload_userfile_token, name='upload_userfile_token'),
    url(r'^upload/userfile/$', views.browser_userupload, name='upload_browserfile'),
    url(r'^transferred/$', views.file_transferred, name='transferred'),
    url(r'^md5/$', views.check_md5_success, name='md5check'),
    url(r'^md5/userfile/$', views.check_md5_success_userfile, name='md5checkuserfile'),
    url(r'^setlibrary/$', views.set_libraryfile, name='setlibfile'),
    url(r'^libfile/$', views.check_libraryfile_ready, name='checklibfile'),
    url(r'^rename/$', views.rename_file),
]
