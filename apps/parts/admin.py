from django.contrib import admin
from .models import Part, AuditLog

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['part_number', 'manufacturer', 'description', 'uom', 'condition', 'is_hazardous', 'status', 'created_at']
    list_filter = ['status', 'condition', 'is_hazardous']
    search_fields = ['part_number', 'manufacturer', 'description', 'tags']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['model_name', 'object_id', 'field_name', 'changed_by', 'timestamp']
    readonly_fields = ['timestamp']
