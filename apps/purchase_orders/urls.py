from django.urls import path
from . import views

urlpatterns = [
    path('', views.po_list, name='po_list'),
    path('create/', views.po_create, name='po_create'),
    path('<int:pk>/', views.po_detail, name='po_detail'),
    path('<int:pk>/edit/', views.po_edit, name='po_edit'),
]
