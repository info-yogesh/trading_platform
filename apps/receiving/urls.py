from django.urls import path
from . import views

urlpatterns = [
    path('', views.receiving_list, name='receiving_list'),
    path('po/<int:po_pk>/receive/', views.receive_po, name='receive_po'),
]
