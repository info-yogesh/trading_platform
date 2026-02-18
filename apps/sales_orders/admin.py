from django.contrib import admin
from .models import SalesOrder, SalesOrderLine

class SOLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ['so_number', 'customer', 'status', 'currency', 'payment_received', 'created_at']
    list_filter = ['status', 'currency', 'payment_received']
    search_fields = ['so_number', 'customer__name', 'customer_po_number']
    readonly_fields = ['so_number', 'created_at', 'updated_at']
    inlines = [SOLineInline]
