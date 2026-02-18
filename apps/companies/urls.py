from django.urls import path
from . import views

urlpatterns = [
    path('', views.company_list, name='company_list'),
    path('create/', views.company_create, name='company_create'),
    path('<int:pk>/', views.company_detail, name='company_detail'),
    path('<int:pk>/edit/', views.company_edit, name='company_edit'),
    path('<int:company_pk>/contacts/add/', views.contact_add, name='contact_add'),
    path('api/search/', views.company_search_api, name='company_search_api'),
]
