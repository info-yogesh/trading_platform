from django.db import models
from django.contrib.auth.models import User


class Part(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
        ('refurbished', 'Refurbished'),
        ('as_is', 'As-Is'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]

    part_number = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=200, blank=True)
    manufacturer_code = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    uom = models.CharField(max_length=50, default='EA', verbose_name='Unit of Measure')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    is_hazardous = models.BooleanField(default=False)
    alternate_pn = models.CharField(max_length=100, blank=True, verbose_name='Alternate Part Number')
    superseded_pn = models.CharField(max_length=100, blank=True, verbose_name='Superseded Part Number')
    internal_notes = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='parts_created')

    class Meta:
        ordering = ['part_number']

    def __str__(self):
        return self.part_number


class AuditLog(models.Model):
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField()
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.model_name} #{self.object_id} - {self.field_name} at {self.timestamp}"
