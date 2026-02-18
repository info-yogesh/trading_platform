from django.db import models
from django.contrib.auth.models import User
from apps.purchase_orders.models import PurchaseOrder, PurchaseOrderLine


class GoodsReceiptNote(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending QC'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    grn_number = models.CharField(max_length=50, unique=True, blank=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='grns')
    received_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    quality_check_passed = models.BooleanField(default=False)
    quality_notes = models.TextField(blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.grn_number:
            import datetime
            today = datetime.date.today()
            count = GoodsReceiptNote.objects.filter(created_at__date=today).count() + 1
            self.grn_number = f"GRN-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.grn_number


class GRNLine(models.Model):
    grn = models.ForeignKey(GoodsReceiptNote, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT)
    quantity_received = models.DecimalField(max_digits=15, decimal_places=4)
    quality_ok = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.grn.grn_number} - {self.po_line}"
