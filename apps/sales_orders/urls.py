from django.urls import path
from . import views

urlpatterns = [
    path('', views.so_list, name='so_list'),
    path('create/', views.so_create, name='so_create'),
    path('<int:pk>/', views.so_detail, name='so_detail'),
    path('<int:pk>/edit/', views.so_edit, name='so_edit'),
]
