# apps/email_integration/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.email_dashboard, name='email_dashboard'),

    # Fetch
    path('fetch/', views.fetch_emails_now, name='email_fetch_now'),
    path('fetch/<int:account_id>/', views.fetch_account_emails, name='email_fetch_account'),

    # Review
    path('verify/<int:email_log_id>/', views.email_verify, name='email_verify'),

    # AJAX — AI parse retry (when parse failed)
    path('verify/<int:email_log_id>/retrigger/', views.retrigger_parse, name='email_retrigger_parse'),

    # AJAX — manual reclassification override
    path('verify/<int:email_log_id>/reclassify/', views.reclassify_email, name='email_reclassify'),

    # Manual paste-and-parse
    path('parse/', views.email_parse, name='email_parse'),

    # Account management
    path('accounts/create/', views.email_account_create, name='email_account_create'),
    path('oauth/start/', views.oauth2_start, name='email_oauth_start'),
    path('oauth/callback/', views.oauth2_callback, name='email_oauth_callback'),
]