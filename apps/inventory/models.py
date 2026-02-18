from django.db import models
from django.contrib.auth.models import User
from apps.parts.models import Part
from apps.companies.models import Company


class InventoryItem(models.Model):
    TYPE_CHOICES = [
        ('own_stock', 'Own Stock'),
        ('vendor_offer', 'Vendor Offer'),
        ('customer_offer', 'Customer Offer'),
        ('push_list', 'Push List'),
    ]
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
        ('refurbished', 'Refurbished'),
        ('as_is', 'As-Is'),
    ]

    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='own_stock')
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='inventory_items')
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_available = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    location = models.CharField(max_length=200, blank=True)
    lead_time = models.CharField(max_length=100, blank=True)
    reference_tag = models.CharField(max_length=200, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    vendor = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='vendor_offers')
    linked_po = models.ForeignKey('purchase_orders.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True)
    linked_so = models.ForeignKey('sales_orders.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.part.part_number} - {self.quantity} {self.item_type}"

    def save(self, *args, **kwargs):
        if self.quantity_available == 0 and self._state.adding:
            self.quantity_available = self.quantity
        super().save(*args, **kwargs)
