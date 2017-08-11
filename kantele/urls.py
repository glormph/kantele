from django.conf.urls import url, include
from django.contrib import admin

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^files/', include('rawstatus.urls')),
    url(r'^datasets/', include('datasets.urls')),

    #url(r'^kantele/$', 'kantele.views.home'),
#    url(r'^kantele/userdatasets/$', 'kantele.views.all_user_datasets'),
#
#
#    url(r'^kantele/dataset/new/$', 'metadata.views.new_dataset'),
#    url(r'^kantele/dataset/edit/(?P<dataset_id>\w+)/$',
#        'metadata.views.edit_dataset'),
#    url(r'^kantele/dataset/copy/(?P<dataset_id>\w+)/$',
#        'metadata.views.copy_dataset'),
#
#    url(r'^kantele/dataset/files/(?P<dataset_id>\w+)/$',
#        'metadata.views.select_files'),
#    url(r'^kantele/dataset/metadata/(?P<dataset_id>\w+)/$',
#        'metadata.views.write_metadata'),
#    url(r'^kantele/dataset/store/(?P<dataset_id>\w+)/$',
#        'metadata.views.store_dataset'),
#
#    url(r'^kantele/dataset/(?P<dataset_id>\w+)/$',
#        'metadata.views.show_dataset'),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    # Uncomment the next line to enable the admin:
    #url(r'^kantele/admin/', include(admin.site.urls)),
]
