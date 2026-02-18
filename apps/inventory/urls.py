from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('create/', views.inventory_create, name='inventory_create'),
    path('<int:pk>/', views.inventory_detail, name='inventory_detail'),
]
