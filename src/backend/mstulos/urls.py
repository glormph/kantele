from django.urls import path
from mstulos import views

app_name = 'mstulos'
urlpatterns = [
        path('', views.frontpage, name='front'),
        path('peptides/', views.peptide_table),
        path('psms/', views.psm_table),
        path('upload/proteins/', views.upload_proteins, name='upload_proteins'),
        path('upload/peptide_proteins/', views.upload_pepprots, name='upload_pepprots'),
        path('upload/peptides/', views.upload_peptides, name='upload_peptides'),
        path('upload/psms/', views.upload_psms, name='upload_psms'),
        path('upload/done/', views.upload_done, name='upload_done'),
        ]

