from django.urls import path
from mstulos import views

app_name = 'mstulos'
urlpatterns = [
        path('', views.frontpage, name='front'),
        path('find/', views.find_query),
        path('result/<str:restype>/<int:resid>/', views.get_results),
        path('data/', views.get_data),
        ]

