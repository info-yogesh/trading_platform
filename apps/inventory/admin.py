from django.contrib import admin
from .models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['part', 'item_type', 'quantity', 'quantity_available', 'cost', 'currency', 'condition', 'location']
    list_filter = ['item_type', 'condition', 'currency']
    search_fields = ['part__part_number', 'description', 'reference_tag']
    readonly_fields = ['created_at', 'updated_at']
