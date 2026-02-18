from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderLine, AdditionalCharge

class POLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1

class ChargeInline(admin.TabularInline):
    model = AdditionalCharge
    extra = 1

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'vendor', 'status', 'currency', 'expected_delivery', 'created_at']
    list_filter = ['status', 'currency']
    search_fields = ['po_number', 'vendor__name']
    readonly_fields = ['po_number', 'created_at', 'updated_at']
    inlines = [POLineInline, ChargeInline]
