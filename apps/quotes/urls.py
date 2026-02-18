from django.urls import path
from . import views

urlpatterns = [
    path('', views.quote_list, name='quote_list'),
    path('create/', views.quote_create, name='quote_create'),
    path('<int:pk>/', views.quote_detail, name='quote_detail'),
    path('<int:pk>/edit/', views.quote_edit, name='quote_edit'),
]
