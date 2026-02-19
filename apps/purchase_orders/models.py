from django.db import models
from django.contrib.auth.models import User
from apps.parts.models import Part
from apps.companies.models import Company
from apps.sales_orders.models import SalesOrder


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('partially_received', 'Partially Received'),
        ('fully_received', 'Fully Received'),
        ('closed', 'Closed'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
    ]

    po_number = models.CharField(max_length=50, blank=True)
    vendor = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='purchase_orders')
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    payment_terms = models.CharField(max_length=200, blank=True)
    delivery_terms = models.CharField(max_length=200, blank=True)
    expected_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.po_number:
            import datetime
            today = datetime.date.today()
            count = PurchaseOrder.objects.filter(created_at__date=today).count() + 1
            self.po_number = f"PO-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.po_number

    @property
    def total_cost(self):
        lines_total = sum(line.line_total for line in self.lines.all())
        charges_total = sum(c.amount for c in self.additional_charges.all())
        return lines_total + charges_total


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    line_number = models.PositiveIntegerField(default=1)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True)
    part_number_raw = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_received = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    cost = models.DecimalField(max_digits=15, decimal_places=4)
    condition = models.CharField(max_length=100, blank=True)
    lead_time = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['line_number']

    @property
    def line_total(self):
        return self.cost * self.quantity


class AdditionalCharge(models.Model):
    ALLOCATION_CHOICES = [
        ('line', 'Specific Line'),
        ('entire_po', 'Entire PO'),
    ]
    TYPE_CHOICES = [
        ('transport', 'Transport'),
        ('customs', 'Customs'),
        ('handling', 'Handling'),
        ('other', 'Other'),
    ]

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='additional_charges')
    charge_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    allocation = models.CharField(max_length=20, choices=ALLOCATION_CHOICES, default='entire_po')
    allocated_to_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"
