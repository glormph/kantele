from django.urls import path
from rawstatus import views


app_name = 'files'
urlpatterns = [
   path('instruments/', views.instrument_page, name='instruments'),
   path('instruments/download/', views.download_instrument_package),
   path('register/', views.register_file, name='register'),
   path('token/', views.request_upload_token, name='req_token'),
   path('instruments/check/', views.instrument_check_in, name='check_in'),
   path('upload/userfile/', views.browser_userupload, name='upload_browserfile'),
   path('transferred/', views.file_transferred, name='transferred'),
   path('transferstate/', views.get_files_transferstate, name='trfstate'),
   path('rename/', views.rename_file),
   path('cleanup/', views.cleanup_old_files),
   path('external/scan/', views.scan_raws_tmp),
   path('external/import/', views.import_external_data),
   path('archive/', views.archive_file),
   path('undelete/', views.restore_file_from_cold),
]
