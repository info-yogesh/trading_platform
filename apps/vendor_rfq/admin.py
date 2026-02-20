from django.contrib import admin
from .models import VendorRFQ, VendorRFQLine, VendorQuoteLine, VendorSuggestionLog


class VendorRFQLineInline(admin.TabularInline):
    model = VendorRFQLine
    extra = 0
    readonly_fields = ['part_number', 'quantity', 'condition']


class VendorQuoteLineInline(admin.TabularInline):
    model = VendorQuoteLine
    extra = 0


@admin.register(VendorRFQ)
class VendorRFQAdmin(admin.ModelAdmin):
    list_display = ['rfq_number', 'inquiry', 'vendor', 'status', 'created_at']
    list_filter = ['status']
    inlines = [VendorRFQLineInline]


@admin.register(VendorRFQLine)
class VendorRFQLineAdmin(admin.ModelAdmin):
    list_display = ['vendor_rfq', 'part_number', 'quantity', 'condition']
    inlines = [VendorQuoteLineInline]


@admin.register(VendorSuggestionLog)
class VendorSuggestionLogAdmin(admin.ModelAdmin):
    list_display = ['inquiry', 'vendor', 'part_number', 'reason', 'created_at']