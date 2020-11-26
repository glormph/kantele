from django.urls import path
from datasets import views

app_name = 'datasets'
urlpatterns = [
    path('new/', views.new_dataset, name="new"),
    path('show/<int:dataset_id>/', views.show_dataset, name="show"),
    path('show/info/<int:dataset_id>/', views.dataset_info),
    path('show/project/<int:project_id>/', views.get_project),
    path('show/files/<int:dataset_id>/', views.dataset_files, name="showfiles"),
    path('find/files/', views.find_files),
    path('show/sampleprep/<int:dataset_id>/', views.dataset_sampleprep, name="showprep"),
    path('show/labelcheck/<int:dataset_id>/', views.labelcheck_samples),
    path('show/pooledlc/<int:dataset_id>/', views.show_pooled_lc),
    path('show/acquisition/<int:dataset_id>/', views.dataset_acquisition, name="showacquisition"),
    path('show/components/<int:datatype_id>/', views.get_datatype_components),
    path('show/species/', views.get_species),
    path('save/project/', views.save_dataset, name="saveproject"),
    path('save/files/', views.save_files, name="savefiles"),
    path('save/acquisition/', views.save_acquisition, name="saveacqui"),
    path('save/sampleprep/', views.save_sampleprep, name="saveprep"),
    path('save/labelcheck/', views.save_labelcheck),
    path('save/pooledlc/', views.save_pooled_lc),
    path('save/owner/', views.change_owners, name="changeowner"),
    path('save/projsample/', views.save_projsample),
    path('archive/dataset/', views.move_dataset_cold),
    path('archive/project/', views.move_project_cold),
    path('undelete/dataset/', views.move_dataset_active),
    path('undelete/project/', views.move_project_active),
    path('purge/project/', views.purge_project),
    path('purge/dataset/', views.purge_dataset),
]
