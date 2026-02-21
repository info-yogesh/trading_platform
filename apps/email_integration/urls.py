from django.urls import path
from . import views

urlpatterns = [
    path('', views.email_dashboard, name='email_dashboard'),
    path('fetch/', views.fetch_emails_now, name='email_fetch_now'),
    path('parse/', views.email_parse, name='email_parse'),
    path('verify/<int:email_log_id>/', views.email_verify, name='email_verify'),
    path('accounts/create/', views.email_account_create, name='email_account_create'),
    path('oauth/start/', views.oauth2_start, name='email_oauth_start'),
    path('oauth/callback/', views.oauth2_callback, name='email_oauth_callback'),
]
