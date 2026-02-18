# email_integration/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class EmailAccount(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    imap_host = models.CharField(max_length=200, blank=True)
    imap_port = models.IntegerField(default=993)
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.IntegerField(default=587)
    use_tls = models.BooleanField(default=True)
    use_oauth2 = models.BooleanField(default=False)

    # OAuth2 tokens (stored encrypted in production — use django-encrypted-model-fields)
    oauth2_access_token = models.TextField(blank=True)
    oauth2_refresh_token = models.TextField(blank=True)
    oauth2_token_expiry = models.DateTimeField(null=True, blank=True)

    # Fetch state
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_history_id = models.CharField(max_length=100, blank=True)  # Gmail API history ID

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_token_expired(self):
        if not self.oauth2_token_expiry:
            return True
        return timezone.now() >= self.oauth2_token_expiry

    def __str__(self):
        return f"{self.name} ({self.email})"


class EmailLog(models.Model):
    DIRECTION_CHOICES = [('inbound', 'Inbound'), ('outbound', 'Outbound')]
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('parsing', 'Parsing'),
        ('parsed', 'Parsed'),
        ('irrelevant', 'Irrelevant'),   # ← new: filtered out
        ('confirmed', 'Confirmed'),     # ← new: user approved
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('sent', 'Sent'),
    ]

    account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, null=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    from_address = models.EmailField()
    to_addresses = models.TextField()
    subject = models.CharField(max_length=500)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    has_attachments = models.BooleanField(default=False)
    parsed_rfq = models.ForeignKey('rfq.RFQ', on_delete=models.SET_NULL, null=True, blank=True)
    gmail_message_id = models.CharField(max_length=200, blank=True, unique=True)  # dedup
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)   # ← new
    relevance_reason = models.TextField(blank=True)              # ← new

    class Meta:
        ordering = ['-received_at']


class ParsedEmailData(models.Model):
    email_log = models.OneToOneField(EmailLog, on_delete=models.CASCADE, related_name='parsed_data')
    raw_parsed = models.JSONField(default=dict)       # raw AI output
    confirmed_lines = models.JSONField(default=list)  # after user edits
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    corrections_made = models.BooleanField(default=False)
    ai_model_used = models.CharField(max_length=100, blank=True)
    parse_duration_ms = models.IntegerField(null=True, blank=True)