from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import InventoryItem
from apps.parts.models import Part
from apps.companies.models import Company


@login_required
def inventory_list(request):
    q = request.GET.get('q', '')
    inv_type = request.GET.get('type', '')
    items = InventoryItem.objects.select_related('part', 'vendor').all()
    if q:
        items = items.filter(Q(part__part_number__icontains=q) | Q(description__icontains=q))
    if inv_type:
        items = items.filter(item_type=inv_type)
    paginator = Paginator(items, 50)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'inventory/list.html', {
        'page': page, 'q': q, 'inv_type': inv_type,
        'type_choices': InventoryItem.TYPE_CHOICES,
    })


@login_required
def inventory_create(request):
    parts = Part.objects.filter(status='active')
    vendors = Company.objects.filter(company_type__in=['vendor', 'both'], is_active=True)
    if request.method == 'POST':
        item = InventoryItem(
            item_type=request.POST.get('item_type', 'own_stock'),
            part_id=request.POST['part'],
            description=request.POST.get('description', ''),
            quantity=request.POST['quantity'],
            cost=request.POST.get('cost') or None,
            currency=request.POST.get('currency', 'USD'),
            condition=request.POST.get('condition', ''),
            location=request.POST.get('location', ''),
            lead_time=request.POST.get('lead_time', ''),
            reference_tag=request.POST.get('reference_tag', ''),
            expiration_date=request.POST.get('expiration_date') or None,
            vendor_id=request.POST.get('vendor') or None,
            internal_notes=request.POST.get('internal_notes', ''),
            created_by=request.user,
        )
        item.save()
        messages.success(request, 'Inventory item added.')
        return redirect('inventory_list')
    return render(request, 'inventory/form.html', {'parts': parts, 'vendors': vendors, 'action': 'Add'})


@login_required
def inventory_detail(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    return render(request, 'inventory/detail.html', {'item': item})
