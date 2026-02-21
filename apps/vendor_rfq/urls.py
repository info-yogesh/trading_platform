# apps/vendor_rfq/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('inquiry/<int:inquiry_pk>/send-to-vendors/', views.send_to_vendors, name='send_to_vendors'),
    path('inquiry/<int:inquiry_pk>/compare/', views.compare_quotes, name='compare_quotes'),  # ← this
    path('<int:pk>/', views.vendor_rfq_detail, name='vendor_rfq_detail'),
    path('<int:pk>/send/', views.vendor_rfq_send, name='vendor_rfq_send'),
    path('<int:pk>/quote/', views.vendor_rfq_quote, name='vendor_rfq_quote'),
    path('verify-quote/<int:parsed_quote_id>/', views.verify_vendor_quote, name='verify_vendor_quote'),
    path('inquiry/<int:inquiry_pk>/debug/', views.debug_inquiry, name='debug_inquiry'),
    path('verify-quote/<int:parsed_quote_id>/retry/', views.retry_parse_vendor_quote, name='retry_parse_vendor_quote'),
]
