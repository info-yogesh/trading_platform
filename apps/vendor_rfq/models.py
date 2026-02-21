from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import re


def generate_vrfq_number():
    last = VendorRFQ.objects.order_by('-id').first()
    next_id = (last.id + 1) if last else 1
    return f"VRFQ-{next_id:04d}"


class VendorRFQ(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_QUOTED = 'quoted'
    STATUS_WON = 'won'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = [
        (STATUS_DRAFT,  'Draft'),
        (STATUS_SENT,   'Sent'),
        (STATUS_QUOTED, 'Quoted'),
        (STATUS_WON,    'Won'),
        (STATUS_LOST,   'Lost'),
    ]

    inquiry = models.ForeignKey('rfq.RFQ', on_delete=models.CASCADE, related_name='vendor_rfqs')
    vendor = models.ForeignKey('companies.Company', on_delete=models.PROTECT, related_name='vendor_rfqs')
    rfq_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Email tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    outbound_email = models.ForeignKey(
        'email_integration.EmailLog', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vendor_rfq_sent'
    )
    # Inbound vendor reply email (for auto-parsing)
    reply_email = models.ForeignKey(
        'email_integration.EmailLog', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vendor_rfq_reply'
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.rfq_number:
            self.rfq_number = generate_vrfq_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rfq_number} → {self.vendor.name}"

    @property
    def is_quoted(self):
        return self.lines.filter(quotes__isnull=False).exists()

    @property
    def total_lines(self):
        return self.lines.count()

    @property
    def quoted_lines(self):
        return self.lines.filter(quotes__isnull=False).count()


class VendorRFQLine(models.Model):
    vendor_rfq = models.ForeignKey(VendorRFQ, on_delete=models.CASCADE, related_name='lines')
    inquiry_line = models.ForeignKey('rfq.RFQLine', on_delete=models.PROTECT, related_name='vendor_lines')
    part_number = models.CharField(max_length=200)
    quantity = models.IntegerField()
    condition = models.CharField(max_length=50, blank=True)
    target_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    line_number = models.IntegerField(default=1)
    is_winner = models.BooleanField(default=False, null=True, blank=True)

    class Meta:
        ordering = ['line_number']
        unique_together = [('vendor_rfq', 'inquiry_line')]  # no duplicate lines per vendor RFQ

    def __str__(self):
        return f"{self.vendor_rfq.rfq_number} / {self.part_number}"

    @property
    def best_quote(self):
        return self.quotes.order_by('unit_price').first()


class VendorQuoteLine(models.Model):
    vendor_rfq_line = models.ForeignKey(VendorRFQLine, on_delete=models.CASCADE, related_name='quotes')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_available = models.IntegerField()
    lead_time_days = models.IntegerField(null=True, blank=True)
    condition = models.CharField(max_length=50, blank=True)
    certification = models.CharField(max_length=200, blank=True)  # e.g. AS9120, CoC
    notes = models.TextField(blank=True)
    # Source of this quote line
    SOURCE_MANUAL = 'manual'
    SOURCE_EMAIL = 'email'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manually Entered'),
        (SOURCE_EMAIL,  'Parsed from Email'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['unit_price']

    def __str__(self):
        return f"{self.vendor_rfq_line} @ {self.unit_price}"

    @property
    def total_value(self):
        return self.unit_price * self.quantity_available


class VendorSuggestionLog(models.Model):
    """Tracks why a vendor was suggested for an inquiry line — for transparency."""
    REASON_QUOTE_HISTORY = 'quote_history'
    REASON_INVENTORY = 'inventory'
    REASON_CATEGORY = 'category'
    REASON_FALLBACK = 'fallback'
    REASON_CHOICES = [
        (REASON_QUOTE_HISTORY, 'Previously Quoted This Part'),
        (REASON_INVENTORY, 'Stocks This Part in Inventory'),
        (REASON_CATEGORY, 'Matched Part Category'),
        (REASON_FALLBACK, 'No Match — Showing All Vendors'),
    ]

    inquiry = models.ForeignKey('rfq.RFQ', on_delete=models.CASCADE)
    vendor = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    part_number = models.CharField(max_length=200)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('inquiry', 'vendor', 'part_number')]


class ParsedVendorQuote(models.Model):
    """Stores AI-parsed vendor quote email, pending user verification."""
    vendor_rfq = models.ForeignKey(VendorRFQ, on_delete=models.CASCADE,
                                       related_name='parsed_quotes')
    email_log = models.OneToOneField('email_integration.EmailLog',
                                          on_delete=models.CASCADE)
    raw_parsed = models.JSONField(default=dict)   # raw AI output
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parsed quote for {self.vendor_rfq.rfq_number}"
