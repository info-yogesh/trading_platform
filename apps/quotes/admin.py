from django.contrib import admin
from .models import Quote, QuoteLine


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 1


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_number', 'customer', 'status', 'currency', 'version', 'created_at']
    list_filter = ['status', 'currency']
    search_fields = ['quote_number', 'customer__name']
    readonly_fields = ['quote_number', 'created_at', 'updated_at']
    inlines = [QuoteLineInline]
