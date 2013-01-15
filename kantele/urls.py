from django.conf.urls import patterns, url, include
from django.contrib import admin
admin.autodiscover()
 
# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^kantele/login/$', 'django.contrib.auth.views.login'),
    url(r'^logout/$', 'metadata.views.logout'),
    
    url(r'^kantele/$', 'kantele.views.home'),
    
    url(r'^kantele/dataset/(?P<dataset_id>\w+)/$', 'metadata.views.show_dataset'),

    url(r'^kantele/dataset/new/$', 'metadata.views.new_dataset'),
    url(r'^kantele/dataset/edit/(?P<dataset_id>\w+)/$', 'metadata.views.edit_dataset'),

    url(r'^kantele/dataset/files/(?P<dataset_id>\w+)/$', 'metadata.views.add_files'),
    url(r'^kantele/dataset/metadata/(?P<dataset_id>\w+)/$', 'metadata.views.write_metadata'),
    url(r'^kantele/dataset/outliers/(?P<dataset_id>\w+)/$', 'metadata.views.define_outliers'),

    url(r'^kantele/store_metadata/$', 'metadata.views.store_dataset'),
    
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    
    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

