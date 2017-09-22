from django.conf.urls import url, include
from django.contrib import admin

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^files/', include('rawstatus.urls')),
    url(r'^datasets/', include('datasets.urls')),
    url(r'^/', include('home.urls')),
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    # Uncomment the next line to enable the admin:
    #url(r'^kantele/admin/', include(admin.site.urls)),
]
