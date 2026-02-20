from django.contrib import admin
from .models import Company, Contact


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_type', 'default_currency', 'payment_terms', 'is_active']
    list_filter = ['company_type', 'is_active', 'default_currency']
    search_fields = ['name', 'tax_id']
    inlines = [ContactInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'company', 'email', 'phone', 'is_primary']
    search_fields = ['first_name', 'last_name', 'email', 'company__name']
