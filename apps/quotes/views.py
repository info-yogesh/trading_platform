from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Quote, QuoteLine
from apps.rfq.models import RFQ
from apps.companies.models import Company
from apps.parts.models import Part


@login_required
def quote_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    quotes = Quote.objects.select_related('customer').all()
    if q:
        quotes = quotes.filter(quote_number__icontains=q)
    if status:
        quotes = quotes.filter(status=status)
    paginator = Paginator(quotes, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'quotes/list.html', {
        'page': page, 'q': q, 'status': status,
        'status_choices': Quote.STATUS_CHOICES,
    })


@login_required
def quote_create(request):
    rfq_id = request.GET.get('rfq')
    rfq = None
    initial_lines = []
    if rfq_id:
        rfq = get_object_or_404(RFQ, pk=rfq_id)
        initial_lines = rfq.lines.all()

    customers = Company.objects.filter(company_type__in=['customer', 'both'], is_active=True)

    if request.method == 'POST':
        quote = Quote(
            customer_id=request.POST['customer'],
            rfq=rfq,
            currency=request.POST.get('currency', 'USD'),
            validity_days=request.POST.get('validity_days', 30),
            payment_terms=request.POST.get('payment_terms', ''),
            delivery_terms=request.POST.get('delivery_terms', ''),
            header_notes=request.POST.get('header_notes', ''),
            footer_notes=request.POST.get('footer_notes', ''),
            template=request.POST.get('template', 'default'),
            created_by=request.user,
        )
        quote.save()

        pn_list = request.POST.getlist('line_pn[]')
        desc_list = request.POST.getlist('line_desc[]')
        qty_list = request.POST.getlist('line_qty[]')
        cost_list = request.POST.getlist('line_cost[]')
        sell_list = request.POST.getlist('line_sell[]')
        lt_list = request.POST.getlist('line_lt[]')

        for i, pn in enumerate(pn_list):
            if not pn:
                continue
            part = Part.objects.filter(part_number=pn).first()
            QuoteLine.objects.create(
                quote=quote,
                line_number=i + 1,
                part=part,
                part_number_raw=pn,
                description=desc_list[i] if i < len(desc_list) else '',
                quantity=qty_list[i] if i < len(qty_list) and qty_list[i] else 0,
                cost=cost_list[i] if i < len(cost_list) and cost_list[i] else None,
                sell_price=sell_list[i] if i < len(sell_list) and sell_list[i] else None,
                lead_time=lt_list[i] if i < len(lt_list) else '',
            )

        messages.success(request, f'Quote {quote.quote_number} created.')
        return redirect('quote_detail', pk=quote.pk)
    return render(request, 'quotes/form.html', {
        'customers': customers, 'rfq': rfq, 'initial_lines': initial_lines, 'action': 'Create',
    })


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    lines = quote.lines.select_related('part').all()
    return render(request, 'quotes/detail.html', {'quote': quote, 'lines': lines})


@login_required
def quote_edit(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    customers = Company.objects.filter(company_type__in=['customer', 'both'], is_active=True)
    if request.method == 'POST':
        quote.currency = request.POST.get('currency', 'USD')
        quote.validity_days = request.POST.get('validity_days', 30)
        quote.payment_terms = request.POST.get('payment_terms', '')
        quote.delivery_terms = request.POST.get('delivery_terms', '')
        quote.header_notes = request.POST.get('header_notes', '')
        quote.footer_notes = request.POST.get('footer_notes', '')
        quote.status = request.POST.get('status', quote.status)
        quote.save()
        messages.success(request, 'Quote updated.')
        return redirect('quote_detail', pk=pk)
    return render(request, 'quotes/form.html', {
        'quote': quote, 'customers': customers, 'action': 'Edit',
    })
