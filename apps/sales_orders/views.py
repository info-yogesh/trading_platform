from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import SalesOrder, SalesOrderLine
from apps.quotes.models import Quote
from apps.companies.models import Company
from apps.parts.models import Part


@login_required
def so_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    orders = SalesOrder.objects.select_related('customer').all()
    if q:
        orders = orders.filter(so_number__icontains=q)
    if status:
        orders = orders.filter(status=status)
    paginator = Paginator(orders, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'sales_orders/list.html', {
        'page': page, 'q': q, 'status': status,
        'status_choices': SalesOrder.STATUS_CHOICES,
    })


@login_required
def so_create(request):
    quote_id = request.GET.get('quote')
    quote = None
    initial_lines = []
    if quote_id:
        quote = get_object_or_404(Quote, pk=quote_id)
        initial_lines = quote.lines.all()

    customers = Company.objects.filter(company_type__in=['customer', 'both'], is_active=True)

    if request.method == 'POST':
        so = SalesOrder(
            customer_id=request.POST['customer'],
            quote=quote,
            currency=request.POST.get('currency', 'USD'),
            payment_terms=request.POST.get('payment_terms', ''),
            delivery_terms=request.POST.get('delivery_terms', ''),
            shipping_address=request.POST.get('shipping_address', ''),
            customer_po_number=request.POST.get('customer_po_number', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        so.save()

        pn_list = request.POST.getlist('line_pn[]')
        qty_list = request.POST.getlist('line_qty[]')
        sell_list = request.POST.getlist('line_sell[]')
        cost_list = request.POST.getlist('line_cost[]')
        desc_list = request.POST.getlist('line_desc[]')

        for i, pn in enumerate(pn_list):
            if not pn:
                continue
            part = Part.objects.filter(part_number=pn).first()
            SalesOrderLine.objects.create(
                sales_order=so,
                line_number=i + 1,
                part=part,
                part_number_raw=pn,
                description=desc_list[i] if i < len(desc_list) else '',
                quantity_ordered=qty_list[i] if qty_list[i] else 0,
                sell_price=sell_list[i] if sell_list[i] else 0,
                cost=cost_list[i] if i < len(cost_list) and cost_list[i] else None,
            )

        messages.success(request, f'Sales Order {so.so_number} created.')
        return redirect('so_detail', pk=so.pk)
    return render(request, 'sales_orders/form.html', {
        'customers': customers, 'quote': quote, 'initial_lines': initial_lines, 'action': 'Create',
    })


@login_required
def so_detail(request, pk):
    so = get_object_or_404(SalesOrder, pk=pk)
    lines = so.lines.select_related('part').all()
    pos = so.purchase_orders.all()
    return render(request, 'sales_orders/detail.html', {'so': so, 'lines': lines, 'pos': pos})


@login_required
def so_edit(request, pk):
    so = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        so.status = request.POST.get('status', so.status)
        so.tracking_number = request.POST.get('tracking_number', '')
        so.payment_received = request.POST.get('payment_received') == 'on'
        so.notes = request.POST.get('notes', '')
        so.save()
        messages.success(request, 'Sales Order updated.')
        return redirect('so_detail', pk=pk)
    return render(request, 'sales_orders/form.html', {'so': so, 'action': 'Edit'})
