from django.contrib import admin
from .models import EmailAccount, EmailLog, ParsedEmailData


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'imap_host', 'imap_port', 'is_active']
    list_filter = ['is_active', 'use_tls', 'use_oauth2']


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['direction', 'from_address', 'subject', 'status', 'has_attachments', 'received_at']
    list_filter = ['direction', 'status', 'has_attachments']
    search_fields = ['from_address', 'subject']
    readonly_fields = ['received_at']
