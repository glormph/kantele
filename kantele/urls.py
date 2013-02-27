from django.conf.urls import patterns, url, include
from django.contrib import admin
admin.autodiscover()
 
# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^kantele/login/$', 'django.contrib.auth.views.login'),
    url(r'^kantele/logout/$', 'kantele.views.logout_page'),
    
    url(r'^kantele/$', 'kantele.views.home'),
    url(r'^kantele/userdatasets/$', 'kantele.views.all_user_datasets'),
    

    url(r'^kantele/dataset/new/$', 'metadata.views.new_dataset'),
    url(r'^kantele/dataset/edit/(?P<dataset_id>\w+)/$', 'metadata.views.edit_dataset'),
    url(r'^kantele/dataset/copy/(?P<dataset_id>\w+)/$', 'metadata.views.copy_dataset'),

    url(r'^kantele/dataset/files/(?P<dataset_id>\w+)/$', 'metadata.views.select_files'),
    url(r'^kantele/dataset/metadata/(?P<dataset_id>\w+)/$', 'metadata.views.write_metadata'),
    url(r'^kantele/dataset/outliers/(?P<dataset_id>\w+)/$', 'metadata.views.define_outliers'),
    url(r'^kantele/dataset/store/(?P<dataset_id>\w+)/$', 'metadata.views.store_dataset'),
    
    url(r'^kantele/dataset/(?P<dataset_id>\w+)/$', 'metadata.views.show_dataset'),

    url(r'^kantele/rawstatus/(?P<fn>\w+)/$', 'rawstatus.views.raw_file_processed'),
    url(r'^kantele/rawstatus/(?P<fn>\w+\.\w+)/$', 'rawstatus.views.raw_file_processed'),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

