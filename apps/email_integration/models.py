# apps/email_integration/models.py
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

    # OAuth2 tokens (store encrypted in production via django-encrypted-model-fields)
    oauth2_access_token = models.TextField(blank=True)
    oauth2_refresh_token = models.TextField(blank=True)
    oauth2_token_expiry = models.DateTimeField(null=True, blank=True)

    # Fetch state
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_history_id = models.CharField(max_length=100, blank=True)  # Gmail history-based sync

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
        ('parse_failed', 'Parse Failed'),   # AI failed — needs manual entry
        ('irrelevant', 'Irrelevant'),
        ('confirmed', 'Confirmed'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('sent', 'Sent'),
    ]

    # ── NEW: email type classification ────────────────────────────────────────
    EMAIL_TYPE_CHOICES = [
        ('new_inquiry',  'New Inquiry'),   # fresh inbound customer RFQ
        ('rfq_reply',    'RFQ Reply'),     # customer replying to our outbound
        ('vendor_reply', 'Vendor Reply'),  # vendor replying to our VRFQ
        ('other',        'Other'),         # not yet classified / irrelevant
    ]
    email_type = models.CharField(
        max_length=20, choices=EMAIL_TYPE_CHOICES, default='other',
        db_index=True,
    )

    # ── NEW: email thread / reply tracking ───────────────────────────────────
    # The RFC 2822 Message-ID of THIS email  e.g. <abc123@mail.gmail.com>
    message_id_header = models.CharField(max_length=500, blank=True, db_index=True)
    # The In-Reply-To header value from THIS email (points to parent message)
    in_reply_to = models.CharField(max_length=500, blank=True, db_index=True)
    # Full References header (space-separated chain of Message-IDs)
    references_header = models.TextField(blank=True)
    # Gmail thread ID (groups all emails in same conversation)
    gmail_thread_id = models.CharField(max_length=200, blank=True, db_index=True)

    # ── NEW: self-reference to the original inquiry email ────────────────────
    # For rfq_reply / vendor_reply emails, points to the first email in the
    # thread (the original inbound inquiry or the original outbound VRFQ).
    linked_inquiry = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='replies',
        help_text="For reply emails: the original inquiry/outbound email this is responding to.",
    )

    # ── Existing fields ───────────────────────────────────────────────────────
    account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, null=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    from_address = models.CharField(max_length=500)   # widened: handles "Name <email>" format
    to_addresses = models.TextField()
    subject = models.CharField(max_length=500)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    has_attachments = models.BooleanField(default=False)
    parsed_rfq = models.ForeignKey(
        'rfq.RFQ', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='email_logs',
    )
    gmail_message_id = models.CharField(max_length=200, blank=True, db_index=True)
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)
    relevance_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"[{self.get_email_type_display()}] {self.subject[:60]}"

    @property
    def is_reply(self):
        return self.email_type in ('rfq_reply', 'vendor_reply')

    @property
    def type_badge_class(self):
        return {
            'new_inquiry':  'badge-open',
            'rfq_reply':    'badge-sent',
            'vendor_reply': 'badge-approved',
            'other':        'badge-closed',
        }.get(self.email_type, 'badge-closed')

    @property
    def display_from(self):
        """Return just the email address portion of from_address."""
        import re
        m = re.search(r'<([^>]+)>', self.from_address)
        return m.group(1) if m else self.from_address


class ParsedEmailData(models.Model):
    email_log = models.OneToOneField(
        EmailLog, on_delete=models.CASCADE, related_name='parsed_data'
    )
    raw_parsed = models.JSONField(default=dict)        # raw AI output
    confirmed_lines = models.JSONField(default=list)   # after user edits / manual entry
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    corrections_made = models.BooleanField(default=False)
    ai_model_used = models.CharField(max_length=100, blank=True)
    parse_duration_ms = models.IntegerField(null=True, blank=True)

    # ── NEW: track whether lines were entered manually (AI failed) ────────────
    manually_entered = models.BooleanField(default=False)

    def __str__(self):
        return f"ParsedData for EmailLog #{self.email_log_id}"