from django.urls import path
from mstulos import views

app_name = 'mstulos'
urlpatterns = [
        path('', views.frontpage, name='front'),
        path('upload/init/', views.init_store_experiment, name='init_store'),
        path('add/<int:nfs_id>/', views.add_analysis),
        path('peptides/', views.peptide_table),
        path('psms/', views.psm_table),
        path('upload/proteins/', views.upload_proteins, name='upload_proteins'),
        path('upload/peptides/', views.upload_peptides, name='upload_peptides'),
        path('upload/psms/', views.upload_psms, name='upload_psms'),
        path('upload/genes/', views.upload_genes, name='upload_geneq'),
        path('upload/done/', views.upload_done, name='upload_done'),
        path('plotdata/peptides/', views.fetch_plotdata_peptides),
        path('plotdata/psms/', views.fetch_plotdata_psms),
        path('plotdata/genes/', views.fetch_plotdata_genes),
        ]

