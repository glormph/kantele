from django.conf.urls import url
from analysis import views


urlpatterns = [
    url(r'^mzml/create$', views.create_mzml),
]
