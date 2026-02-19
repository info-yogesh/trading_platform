from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import RFQ, RFQLine, RFQAuditLog
from apps.companies.models import Company
from apps.parts.models import Part


@login_required
def rfq_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    rfqs = RFQ.objects.select_related('customer', 'assigned_to').all()
    if q:
        rfqs = rfqs.filter(Q(rfq_number__icontains=q) | Q(customer__name__icontains=q))
    if status:
        rfqs = rfqs.filter(status=status)
    paginator = Paginator(rfqs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'rfq/list.html', {
        'page': page, 'q': q, 'status': status,
        'status_choices': RFQ.STATUS_CHOICES,
    })


@login_required
def rfq_create(request):
    import json
    customers = Company.objects.filter(company_type__in=['customer', 'both'], is_active=True)

    # Read prefill from session
    prefill = {}
    prefill_customer = None
    prefill_raw = request.session.pop('rfq_prefill', None)
    if prefill_raw:
        try:
            prefill = json.loads(prefill_raw)
        except (json.JSONDecodeError, TypeError):
            prefill = {}

    # ✅ Resolve or create the customer from prefill
    if prefill.get('customer_name'):
        customer_name = prefill['customer_name'].strip()

        # Try to find existing company by name (case-insensitive)
        prefill_customer = Company.objects.filter(
            name__iexact=customer_name,
            company_type__in=['customer', 'both'],
        ).first()

        if not prefill_customer:
            # Auto-create with minimal info — user can enrich later
            prefill_customer = Company.objects.create(
                name=customer_name,
                company_type='customer',
                is_active=True,
            )
            messages.info(
                request,
                f'New customer "{customer_name}" was automatically created from the email. '
                f'Please review and complete their profile.'
            )

        # Make sure it appears in the dropdown queryset
        customers = Company.objects.filter(
            company_type__in=['customer', 'both'], is_active=True
        )

    if request.method == 'POST':
        rfq = RFQ(
            customer_id=request.POST['customer'],
            payment_terms=request.POST.get('payment_terms', ''),
            delivery_address=request.POST.get('delivery_address', ''),
            source=request.POST.get('source', 'manual'),
            internal_notes=request.POST.get('internal_notes', ''),
            external_notes=request.POST.get('external_notes', ''),
            created_by=request.user,
        )
        rfq.save()

        pn_list   = request.POST.getlist('line_pn[]')
        desc_list = request.POST.getlist('line_desc[]')
        qty_list  = request.POST.getlist('line_qty[]')
        cd_list   = request.POST.getlist('line_cd[]')

        for i, pn in enumerate(pn_list):
            if not pn.strip():
                continue
            part = Part.objects.filter(part_number=pn).first()
            RFQLine.objects.create(
                rfq=rfq,
                line_number=i + 1,
                part=part,
                part_number_raw=pn,
                description=desc_list[i] if i < len(desc_list) else '',
                quantity=qty_list[i] if i < len(qty_list) and qty_list[i] else 0,
                condition_required=cd_list[i] if i < len(cd_list) else '',
            )

        messages.success(request, f'RFQ {rfq.rfq_number} created.')
        return redirect('rfq_detail', pk=rfq.pk)

    return render(request, 'rfq/form.html', {
        'customers': customers,
        'action': 'Create',
        'prefill': prefill,
        'prefill_customer': prefill_customer,   # ✅ new
        'prefill_customer_created': getattr(prefill_customer, '_just_created', False),  # ✅

    })

@login_required
def rfq_detail(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    lines = rfq.lines.select_related('part').all()
    audit_logs = rfq.audit_logs.select_related('changed_by').all()[:20]

    # Vendor RFQs for this inquiry
    vendor_rfqs = rfq.vendor_rfqs.select_related(
        'vendor', 'created_by'
    ).prefetch_related('lines__quotes').all()

    # Summary stats per vendor RFQ
    vendor_rfq_stats = []
    for vrfq in vendor_rfqs:
        total   = vrfq.lines.count()
        quoted  = vrfq.lines.filter(quotes__isnull=False).distinct().count()
        vendor_rfq_stats.append({
            'vrfq': vrfq,
            'total_lines': total,
            'quoted_lines': quoted,
            'progress': int((quoted / total * 100)) if total else 0,
        })

    return render(request, 'rfq/detail.html', {
        'rfq': rfq,
        'lines': lines,
        'audit_logs': audit_logs,
        'vendor_rfq_stats': vendor_rfq_stats,
        'has_vendor_rfqs': vendor_rfqs.exists(),
    })


@login_required
def rfq_edit(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    customers = Company.objects.filter(company_type__in=['customer', 'both'], is_active=True)
    if request.method == 'POST':
        old_status = rfq.status
        rfq.payment_terms = request.POST.get('payment_terms', '')
        rfq.delivery_address = request.POST.get('delivery_address', '')
        rfq.internal_notes = request.POST.get('internal_notes', '')
        rfq.external_notes = request.POST.get('external_notes', '')
        rfq.status = request.POST.get('status', rfq.status)
        rfq.save()
        if old_status != rfq.status:
            RFQAuditLog.objects.create(
                rfq=rfq, changed_by=request.user,
                field_changed='status', old_value=old_status, new_value=rfq.status,
            )
        messages.success(request, 'RFQ updated.')
        return redirect('rfq_detail', pk=pk)
    return render(request, 'rfq/form.html', {'rfq': rfq, 'customers': customers, 'action': 'Edit'})


@login_required
def rfq_paste_parse(request):
    """Parse pasted text into RFQ lines."""
    if request.method == 'POST':
        text = request.POST.get('paste_text', '')
        lines = []
        for row in text.strip().split('\n'):
            parts = row.split('\t') if '\t' in row else row.split(',')
            if len(parts) >= 1:
                lines.append({
                    'pn': parts[0].strip(),
                    'description': parts[1].strip() if len(parts) > 1 else '',
                    'qty': parts[2].strip() if len(parts) > 2 else '',
                    'cd': parts[3].strip() if len(parts) > 3 else '',
                })
        return JsonResponse({'lines': lines})
    return JsonResponse({'error': 'POST required'}, status=400)
