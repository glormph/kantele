from django.conf.urls import patterns, include, url

 
# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^kantele/$', 'metadata.views.process_metadata_input'),

    url(r'^kantele/newdataset/$', 'metadata.views.new_dataset'),
    url(r'^kantele/store_metadata/$', 'metadata.views.store_dataset'),
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)

