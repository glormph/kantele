from django.conf.urls import url
from rawstatus import views


urlpatterns = [
    url(r'^register/$', views.register_file),
    url(r'^transferred/$', views.file_transferred),
]
