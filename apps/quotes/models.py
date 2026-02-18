from django.db import models
from django.contrib.auth.models import User
from apps.rfq.models import RFQ, RFQLine
from apps.parts.models import Part
from apps.companies.models import Company


class Quote(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
    ]

    quote_number = models.CharField(max_length=50, unique=True, blank=True)
    rfq = models.ForeignKey(RFQ, on_delete=models.PROTECT, related_name='quotes', null=True, blank=True)
    customer = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='quotes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    validity_days = models.IntegerField(default=30)
    payment_terms = models.CharField(max_length=200, blank=True)
    delivery_terms = models.CharField(max_length=200, blank=True)
    header_notes = models.TextField(blank=True)
    footer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    template = models.CharField(max_length=50, default='default')
    version = models.IntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='quotes_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.quote_number:
            import datetime
            today = datetime.date.today()
            count = Quote.objects.filter(created_at__date=today).count() + 1
            self.quote_number = f"QUO-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.quote_number

    @property
    def total_sell(self):
        return sum(line.sell_price * line.quantity for line in self.lines.all() if line.sell_price)

    @property
    def total_cost(self):
        return sum((line.cost or 0) * line.quantity for line in self.lines.all())

    @property
    def total_margin(self):
        sell = self.total_sell
        cost = self.total_cost
        if sell:
            return round((sell - cost) / sell * 100, 2)
        return 0


class QuoteLine(models.Model):
    COST_SOURCE_CHOICES = [
        ('inventory', 'From Inventory'),
        ('vendor_offer', 'Vendor Offer'),
        ('manual', 'Manual Entry'),
    ]

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='lines')
    rfq_line = models.ForeignKey(RFQLine, on_delete=models.SET_NULL, null=True, blank=True)
    line_number = models.PositiveIntegerField(default=1)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True)
    part_number_raw = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    condition = models.CharField(max_length=100, blank=True)
    cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    cost_source = models.CharField(max_length=20, choices=COST_SOURCE_CHOICES, default='manual')
    sell_price = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    lead_time = models.CharField(max_length=100, blank=True)
    reference_tag = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['line_number']

    @property
    def margin_percent(self):
        if self.sell_price and self.cost and self.sell_price > 0:
            return round((self.sell_price - self.cost) / self.sell_price * 100, 2)
        return None

    @property
    def line_total(self):
        if self.sell_price and self.quantity:
            return self.sell_price * self.quantity
        return 0
