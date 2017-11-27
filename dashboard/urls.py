from django.conf.urls import url
from dashboard import views


app_name = 'dash'
urlpatterns = [
    url(r'^jobs/$', views.show_jobs, name='jobs'),
]
