from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import PurchaseOrder, PurchaseOrderLine, AdditionalCharge
from apps.companies.models import Company
from apps.sales_orders.models import SalesOrder
from apps.parts.models import Part


@login_required
def po_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    orders = PurchaseOrder.objects.select_related('vendor').all()
    if q:
        orders = orders.filter(po_number__icontains=q)
    if status:
        orders = orders.filter(status=status)
    paginator = Paginator(orders, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'purchase_orders/list.html', {
        'page': page, 'q': q, 'status': status,
        'status_choices': PurchaseOrder.STATUS_CHOICES,
    })


@login_required
def po_create(request):
    so_id = request.GET.get('so')
    so = None
    if so_id:
        so = get_object_or_404(SalesOrder, pk=so_id)

    vendors = Company.objects.filter(company_type__in=['vendor', 'both'], is_active=True)

    if request.method == 'POST':
        po = PurchaseOrder(
            vendor_id=request.POST['vendor'],
            sales_order=so,
            currency=request.POST.get('currency', 'USD'),
            payment_terms=request.POST.get('payment_terms', ''),
            delivery_terms=request.POST.get('delivery_terms', ''),
            expected_delivery=request.POST.get('expected_delivery') or None,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        po.save()

        pn_list = request.POST.getlist('line_pn[]')
        qty_list = request.POST.getlist('line_qty[]')
        cost_list = request.POST.getlist('line_cost[]')
        desc_list = request.POST.getlist('line_desc[]')

        for i, pn in enumerate(pn_list):
            if not pn:
                continue
            part = Part.objects.filter(part_number=pn).first()
            PurchaseOrderLine.objects.create(
                purchase_order=po,
                line_number=i + 1,
                part=part,
                part_number_raw=pn,
                description=desc_list[i] if i < len(desc_list) else '',
                quantity=qty_list[i] if qty_list[i] else 0,
                cost=cost_list[i] if cost_list[i] else 0,
            )

        # Additional charges
        charge_types = request.POST.getlist('charge_type[]')
        charge_descs = request.POST.getlist('charge_desc[]')
        charge_amounts = request.POST.getlist('charge_amount[]')
        charge_allocs = request.POST.getlist('charge_allocation[]')

        for i, ct in enumerate(charge_types):
            if ct and i < len(charge_amounts) and charge_amounts[i]:
                AdditionalCharge.objects.create(
                    purchase_order=po,
                    charge_type=ct,
                    description=charge_descs[i] if i < len(charge_descs) else '',
                    amount=charge_amounts[i],
                    allocation=charge_allocs[i] if i < len(charge_allocs) else 'entire_po',
                )

        messages.success(request, f'Purchase Order {po.po_number} created.')
        return redirect('po_detail', pk=po.pk)
    return render(request, 'purchase_orders/form.html', {
        'vendors': vendors, 'so': so, 'action': 'Create',
    })


@login_required
def po_detail(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    lines = po.lines.select_related('part').all()
    charges = po.additional_charges.all()
    grns = po.grns.all()
    return render(request, 'purchase_orders/detail.html', {
        'po': po, 'lines': lines, 'charges': charges, 'grns': grns,
    })


@login_required
def po_edit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        po.status = request.POST.get('status', po.status)
        po.notes = request.POST.get('notes', '')
        po.expected_delivery = request.POST.get('expected_delivery') or None
        po.save()
        messages.success(request, 'Purchase Order updated.')
        return redirect('po_detail', pk=pk)
    vendors = Company.objects.filter(company_type__in=['vendor', 'both'], is_active=True)
    return render(request, 'purchase_orders/form.html', {'po': po, 'vendors': vendors, 'action': 'Edit'})
