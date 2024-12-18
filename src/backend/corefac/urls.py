from django.urls import path
from corefac import views


app_name = 'corefac'
urlpatterns = [
    path('', views.corefac_home, name='home'),
    path('sampleprep/method/add/', views.add_sampleprep_method),
    path('sampleprep/version/add/', views.add_sampleprep_method_version),
    path('sampleprep/method/edit/', views.edit_sampleprep_method),
    path('sampleprep/version/edit/', views.edit_sampleprep_method_version),
    path('sampleprep/method/disable/', views.disable_sampleprep_method),

    path('sampleprep/version/disable/', views.disable_sampleprep_method_version),
    path('sampleprep/method/enable/', views.enable_sampleprep_method),
    path('sampleprep/version/enable/', views.enable_sampleprep_method_version),
    path('sampleprep/method/delete/', views.delete_sampleprep_method),
    path('sampleprep/version/delete/', views.delete_sampleprep_method_version),

    path('sampleprep/pipeline/add/', views.add_sampleprep_pipeline),
    path('sampleprep/pipeline/edit/', views.edit_sampleprep_pipeline),
    path('sampleprep/pipeline/lock/', views.lock_sampleprep_pipeline),
    path('sampleprep/pipeline/disable/', views.disable_sampleprep_pipeline),
    path('sampleprep/pipeline/enable/', views.enable_sampleprep_pipeline),
    path('sampleprep/pipeline/delete/', views.delete_sampleprep_pipeline),
]
