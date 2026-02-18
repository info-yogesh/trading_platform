from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    TYPE_CHOICES = [
        ('vendor', 'Vendor'),
        ('customer', 'Customer'),
        ('both', 'Both'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('AED', 'UAE Dirham'),
    ]

    name = models.CharField(max_length=200)
    company_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='customer')
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    default_currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return self.name


class Contact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.company.name})"
