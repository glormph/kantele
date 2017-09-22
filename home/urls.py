from django.conf.urls import url
from home import views

app_name = 'home'
urlpatterns = [
    url(r'^home/$', views.home, name="home"),
    url(r'^show/datasets/$', views.show_datasets, name="showdatasets"),
]
