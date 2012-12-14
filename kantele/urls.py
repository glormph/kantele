from django.conf.urls import patterns, url, include
from django.contrib import admin
admin.autodiscover()
 
# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^kantele/$', 'kantele.views.home'),
    url(r'^kantele/newdataset/$', 'metadata.views.new_dataset'),
    url(r'^login/$', 'django.contrib.auth.views.login'),
    url(r'^logout/$', 'metadata.views.logout'),
    url(r'^kantele/store_metadata/$', 'metadata.views.store_dataset'),
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

