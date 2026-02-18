from django.urls import path
from . import views

urlpatterns = [
    path('', views.part_list, name='part_list'),
    path('create/', views.part_create, name='part_create'),
    path('<int:pk>/', views.part_detail, name='part_detail'),
    path('<int:pk>/edit/', views.part_edit, name='part_edit'),
    path('bulk-upload/', views.part_bulk_upload, name='part_bulk_upload'),
    path('api/search/', views.part_search_api, name='part_search_api'),
]
