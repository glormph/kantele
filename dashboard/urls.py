from django.urls import path
from dashboard import views


app_name = 'dashboard'
urlpatterns = [
    path('', views.dashboard, name='dash'),
    path('longqc/<int:instrument_id>', views.show_qc, name='longqc'),
    path('proddata', views.get_file_production),
]
