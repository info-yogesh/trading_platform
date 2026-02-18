from django.contrib import admin
from .models import GoodsReceiptNote, GRNLine

class GRNLineInline(admin.TabularInline):
    model = GRNLine
    extra = 1

@admin.register(GoodsReceiptNote)
class GRNAdmin(admin.ModelAdmin):
    list_display = ['grn_number', 'purchase_order', 'received_date', 'status', 'quality_check_passed', 'received_by']
    list_filter = ['status', 'quality_check_passed']
    search_fields = ['grn_number', 'purchase_order__po_number']
    readonly_fields = ['grn_number', 'created_at']
    inlines = [GRNLineInline]
