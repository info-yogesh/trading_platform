from django.db import models
from django.contrib.auth.models import User
from apps.parts.models import Part
from apps.companies.models import Company


class RFQ(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('waiting_vendor', 'Waiting Vendor Response'),
        ('partially_quoted', 'Partially Quoted'),
        ('fully_quoted', 'Fully Quoted'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('closed', 'Closed'),
    ]
    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('email', 'Email'),
        ('bulk_paste', 'Bulk Paste'),
        ('ai_parsed', 'AI Parsed'),
    ]

    rfq_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='rfqs')
    date_received = models.DateField(auto_now_add=True)
    payment_terms = models.CharField(max_length=200, blank=True)
    delivery_address = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    internal_notes = models.TextField(blank=True)
    external_notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_rfqs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_rfqs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RFQ'
        verbose_name_plural = 'RFQs'

    def save(self, *args, **kwargs):
        if not self.rfq_number:
            import datetime
            today = datetime.date.today()
            count = RFQ.objects.filter(created_at__date=today).count() + 1
            self.rfq_number = f"RFQ-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.rfq_number

    @property
    def line_count(self):
        return self.lines.count()

    @property
    def quoted_line_count(self):
        return self.lines.filter(line_status='quoted').count()


class RFQLine(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('quoted', 'Quoted'),
        ('no_offer', 'No Offer'),
        ('cancelled', 'Cancelled'),
    ]

    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='lines')
    line_number = models.PositiveIntegerField(default=1)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True)
    part_number_raw = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    condition_required = models.CharField(max_length=100, blank=True, verbose_name='CD')
    target_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    line_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['line_number']

    def __str__(self):
        return f"{self.rfq.rfq_number} - Line {self.line_number}"


class RFQAuditLog(models.Model):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='audit_logs')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    field_changed = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
