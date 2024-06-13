from django.urls import path
from home import views

app_name = 'home'
urlpatterns = [
    path('', views.home, name="home"),
    path('show/datasets/', views.show_datasets, name="showdatasets"),
    path('show/projects/', views.show_projects, name="showprojects"),
    path('show/analyses/', views.show_analyses, name="showanalyses"),
    path('show/jobs/', views.show_jobs, name="showjobs"),
    path('show/files/', views.show_files, name="showfiles"),
    path('find/datasets/', views.find_datasets, name="finddatasets"),
    path('find/projects/', views.find_projects, name="findprojects"),
    path('find/analyses/', views.find_analysis, name="findanalyses"),
    path('find/files/', views.find_files, name="findfiles"),
    path('show/dataset/<int:dataset_id>', views.get_dset_info, name="dsinfo"),
    path('show/project/<int:proj_id>', views.get_proj_info, name="projinfo"),
    path('show/file/<int:file_id>', views.get_file_info, name="fninfo"),
    path('show/analysis/<int:nfs_id>', views.get_analysis_info, name="anainfo"),
    path('show/job/<int:job_id>', views.get_job_info, name="jobinfo"),
    path('messages/', views.show_messages, name="messages"),
    path('refresh/job/<int:job_id>', views.refresh_job, name="jobrefresh"),
    path('refresh/analysis/<int:nfs_id>', views.refresh_analysis, name="analysisrefresh"),
    path('createmzml/', views.create_mzmls),
    path('refinemzml/', views.refine_mzmls),
]
