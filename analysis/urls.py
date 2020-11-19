from django.urls import path
from analysis import views


app_name = 'analysis'
urlpatterns = [
    path('new/', views.get_analysis_init),
    path('<int:anid>/', views.get_analysis),
    path('store/', views.store_analysis),
    path('delete/', views.delete_analysis),
    path('stop/', views.stop_analysis),
    path('start/', views.start_analysis),
    path('undelete/', views.undelete_analysis),
    path('purge/', views.purge_analysis),
    path('dsets/', views.get_datasets),
    path('baseanalysis/show/', views.get_base_analyses),
    path('baseanalysis/load/<int:anid>/', views.load_base_analysis),
    path('workflow/', views.get_workflow_versioned),
    path('workflows/', views.get_allwfs),
    path('logappend/', views.append_analysis_log, name='appendlog'),
    path('log/<int:nfs_id>', views.show_analysis_log),
    path('showfile/<int:file_id>', views.serve_analysis_file),
    path('fastarelease/check/', views.check_fasta_release, name='checkfastarelease'),
    path('fastarelease/set/', views.set_protein_database_lib, name='setfastarelease'),
]
