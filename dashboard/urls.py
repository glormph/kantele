from django.conf.urls import url
from dashboard import views


app_name = 'dash'
urlpatterns = [
    url(r'^$', views.dashboard, name='dash'),
    url(r'^jobs/$', views.show_jobs, name='jobs'),
    url(r'^qc/$', views.show_qc, name='qc'),
    url(r'^qc/store/$', views.store_longitudinal_qc, name='storeqc'),
]
