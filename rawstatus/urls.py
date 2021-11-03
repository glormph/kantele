from django.urls import path
from rawstatus import views


app_name = 'files'
urlpatterns = [
   path('', views.show_files, name='latestfiles'),
   path('instruments/', views.instrument_page, name='instruments'),
   path('instruments/download/', views.download_instrument_package),
   path('register/', views.register_file, name='register'),
   path('register/userfile/', views.register_userupload, name='registeruserupload'),
   path('userfile/', views.request_token_userupload, name='req_userupload'),
   path('upload/token/', views.upload_userfile_token, name='upload_userfile_token'),
   path('upload/userfile/', views.browser_userupload, name='upload_browserfile'),
   path('transferred/', views.file_transferred, name='transferred'),
   path('transferstate/', views.get_files_transferstate, name='trfstate'),
   path('md5/', views.check_md5_success, name='md5check'),
   path('md5/userfile/', views.check_md5_success_userfile, name='md5checkuserfile'),
   path('setlibrary/', views.set_libraryfile, name='setlibfile'),
   path('libfile/', views.check_libraryfile_ready, name='checklibfile'),
   path('rename/', views.rename_file),
   path('cleanup/', views.cleanup_old_files),
   path('external/scan/', views.scan_raws_tmp),
   path('external/import/', views.import_external_data),
   path('archive/', views.archive_file),
   path('undelete/', views.restore_file_from_cold),
   path('purge/', views.delete_file_from_cold),
]
