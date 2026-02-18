from django.db import models
from django.contrib.auth.models import User
from apps.parts.models import Part
from apps.companies.models import Company
from apps.quotes.models import Quote


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('waiting_po', 'Waiting PO'),
        ('partially_received', 'Partially Received'),
        ('ready_to_ship', 'Ready to Ship'),
        ('shipped', 'Shipped'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
    ]

    so_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='sales_orders')
    quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_orders')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    payment_terms = models.CharField(max_length=200, blank=True)
    delivery_terms = models.CharField(max_length=200, blank=True)
    shipping_address = models.TextField(blank=True)
    customer_po_number = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)
    payment_received = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.so_number:
            import datetime
            today = datetime.date.today()
            count = SalesOrder.objects.filter(created_at__date=today).count() + 1
            self.so_number = f"SO-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.so_number

    @property
    def total_value(self):
        return sum(line.line_total for line in self.lines.all())

    @property
    def total_profit(self):
        return sum(line.profit for line in self.lines.all())


class SalesOrderLine(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('allocated', 'Allocated'),
        ('partially_shipped', 'Partially Shipped'),
        ('shipped', 'Shipped'),
        ('cancelled', 'Cancelled'),
    ]

    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='lines')
    line_number = models.PositiveIntegerField(default=1)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True)
    part_number_raw = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    quantity_ordered = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_shipped = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    condition = models.CharField(max_length=100, blank=True)
    sell_price = models.DecimalField(max_digits=15, decimal_places=4)
    cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    allocated_charges = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    lead_time = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['line_number']

    @property
    def line_total(self):
        return self.sell_price * self.quantity_ordered

    @property
    def profit(self):
        if self.cost is not None:
            return (self.sell_price - self.cost - self.allocated_charges) * self.quantity_ordered
        return 0

    @property
    def margin_percent(self):
        if self.sell_price and self.sell_price > 0 and self.cost is not None:
            net = self.sell_price - self.cost - self.allocated_charges
            return round(net / self.sell_price * 100, 2)
        return None
