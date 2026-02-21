from django.contrib import admin
from .models import RFQ, RFQLine, RFQAuditLog


class RFQLineInline(admin.TabularInline):
    model = RFQLine
    extra = 1


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ['rfq_number', 'customer', 'date_received', 'status', 'source', 'created_by']
    list_filter = ['status', 'source']
    search_fields = ['rfq_number', 'customer__name']
    readonly_fields = ['rfq_number', 'created_at', 'updated_at']
    inlines = [RFQLineInline]


@admin.register(RFQLine)
class RFQLineAdmin(admin.ModelAdmin):
    list_display = ['rfq', 'line_number', 'part_number_raw', 'quantity', 'line_status']
    list_filter = ['line_status']
    search_fields = ['rfq__rfq_number', 'part_number_raw']
