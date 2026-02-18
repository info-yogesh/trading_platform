from django.urls import path
from . import views

urlpatterns = [
    path('', views.rfq_list, name='rfq_list'),
    path('create/', views.rfq_create, name='rfq_create'),
    path('<int:pk>/', views.rfq_detail, name='rfq_detail'),
    path('<int:pk>/edit/', views.rfq_edit, name='rfq_edit'),
    path('api/parse-paste/', views.rfq_paste_parse, name='rfq_paste_parse'),
]
