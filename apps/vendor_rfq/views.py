from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from collections import defaultdict

from apps.rfq.models import RFQ, RFQLine
from apps.companies.models import Company
from .models import VendorRFQ, VendorRFQLine, VendorQuoteLine
from .suggestion_engine import get_vendor_suggestions, save_suggestion_log


# ─────────────────────────────────────────────
# Phase 3: Vendor Selection Grid
# ─────────────────────────────────────────────

@login_required
def send_to_vendors(request, inquiry_pk):
    inquiry = get_object_or_404(RFQ, pk=inquiry_pk)
    lines = inquiry.lines.all()

    suggested, all_vendors, reasons = get_vendor_suggestions(inquiry)

    if request.method == 'POST':
        # POST data shape:
        # vendor_<vendor_id>_line_<line_id> = 'on'  → this vendor gets this line
        created_count = 0

        for vendor in all_vendors:
            # Collect which lines are checked for this vendor
            assigned_line_ids = []
            for line in lines:
                key = f'vendor_{vendor.pk}_line_{line.pk}'
                if request.POST.get(key):
                    assigned_line_ids.append(line.pk)

            if not assigned_line_ids:
                continue  # vendor not selected at all

            # Check if a draft VendorRFQ already exists for this vendor+inquiry
            vrfq, created = VendorRFQ.objects.get_or_create(
                inquiry=inquiry,
                vendor=vendor,
                status=VendorRFQ.STATUS_DRAFT,
                defaults={'created_by': request.user},
            )

            # Clear old lines if re-submitting
            if not created:
                vrfq.lines.all().delete()

            # Create lines
            for i, line_id in enumerate(assigned_line_ids, start=1):
                rfq_line = RFQLine.objects.get(pk=line_id)
                VendorRFQLine.objects.create(
                    vendor_rfq=vrfq,
                    inquiry_line=rfq_line,
                    part_number=rfq_line.part_number_raw,
                    quantity=rfq_line.quantity,
                    condition=rfq_line.condition_required,
                    line_number=i,
                )

            created_count += 1

        # Save suggestion audit log
        save_suggestion_log(inquiry, suggested, reasons)

        messages.success(
            request,
            f'{created_count} vendor RFQ draft{"s" if created_count != 1 else ""} created. '
            f'Review and send each one from the inquiry page.'
        )
        return redirect('rfq_detail', pk=inquiry_pk)

    # Build suggestion map: vendor_id → set of line ids suggested
    suggested_line_ids = defaultdict(set)
    for vendor_id, pn_set in suggested.items():
        for line in lines:
            if line.part_number_raw in pn_set:
                suggested_line_ids[vendor_id].add(line.pk)

    # Already-created vendor RFQs for this inquiry (to show existing state)
    existing_vrfqs = {
        vrfq.vendor_id: vrfq
        for vrfq in VendorRFQ.objects.filter(inquiry=inquiry).prefetch_related('lines')
    }
    existing_line_ids = defaultdict(set)
    for vendor_id, vrfq in existing_vrfqs.items():
        for vline in vrfq.lines.all():
            existing_line_ids[vendor_id].add(vline.inquiry_line_id)

    return render(request, 'vendor_rfq/send_to_vendors.html', {
        'inquiry': inquiry,
        'lines': lines,
        'all_vendors': all_vendors,
        'suggested_line_ids': {k: list(v) for k, v in suggested_line_ids.items()},
        'existing_line_ids': {k: list(v) for k, v in existing_line_ids.items()},
        'existing_vrfqs': existing_vrfqs,
        'reasons': reasons,
    })


# ─────────────────────────────────────────────
# Phase 4a: VendorRFQ Detail
# ─────────────────────────────────────────────

@login_required
def vendor_rfq_detail(request, pk):
    vrfq  = get_object_or_404(VendorRFQ.objects.select_related(
        'inquiry', 'vendor', 'created_by'
    ).prefetch_related('lines__inquiry_line', 'lines__quotes'), pk=pk)

    return render(request, 'vendor_rfq/detail.html', {'vrfq': vrfq})


# ─────────────────────────────────────────────
# Phase 4b: Send Email to Vendor
# ─────────────────────────────────────────────

@login_required
def vendor_rfq_send(request, pk):
    vrfq = get_object_or_404(VendorRFQ, pk=pk)

    if vrfq.status != VendorRFQ.STATUS_DRAFT:
        messages.warning(request, 'This RFQ has already been sent.')
        return redirect('vendor_rfq_detail', pk=pk)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip() + f" (RFQ Number: {vrfq.rfq_number})"
        body = request.POST.get('body', '').strip()
        vendor_email = request.POST.get('vendor_email', '').strip()

        if not vendor_email:
            messages.error(request, 'Vendor email address is required.')
            return redirect('vendor_rfq_send', pk=pk)

        # Send via Gmail OAuth using the first active OAuth account
        try:
            from apps.email_integration.models import EmailAccount, EmailLog
            from apps.email_integration.gmail_sender import send_email

            account = EmailAccount.objects.filter(
                is_active=True, use_oauth2=True
            ).first()

            if not account:
                messages.error(request, 'No Gmail account configured. Add one in Email settings.')
                return redirect('vendor_rfq_send', pk=pk)

            send_email(
                account=account,
                to=vendor_email,
                subject=subject,
                body=body,
            )

            # Log the outbound email
            email_log = EmailLog.objects.create(
                account=account,
                direction='outbound',
                from_address=account.email,
                to_addresses=vendor_email,
                subject=subject,
                body_text=body,
                status='sent',
                received_at=timezone.now(),
            )

            vrfq.status = VendorRFQ.STATUS_SENT
            vrfq.sent_at = timezone.now()
            vrfq.outbound_email = email_log
            vrfq.save()

            messages.success(request, f'RFQ sent to {vendor_email}.')
            return redirect('vendor_rfq_detail', pk=pk)

        except Exception as e:
            messages.error(request, f'Failed to send email: {str(e)}')
            return redirect('vendor_rfq_send', pk=pk)

    # GET — render the email draft preview
    default_subject = f"RFQ {vrfq.rfq_number} – Component Inquiry"
    default_body = _build_rfq_email_body(vrfq)
    primary_contact = vrfq.vendor.contacts.filter(is_primary=True).first()
    vendor_email = primary_contact.email if primary_contact else ''

    return render(request, 'vendor_rfq/send_email.html', {
        'vrfq': vrfq,
        'default_subject': default_subject,
        'default_body': default_body,
        'vendor_email': vendor_email,
    })


def _build_rfq_email_body(vrfq):
    """Build the default plain-text email body for a vendor RFQ."""
    lines_text = '\n'.join([
        f"  {i}. {l.part_number}  |  Qty: {l.quantity}  |  Condition: {l.condition or 'Any'}"
        f"{'  |  Target: $' + str(l.target_price) if l.target_price else ''}"
        for i, l in enumerate(vrfq.lines.all(), start=1)
    ])

    return f"""Dear {vrfq.vendor.name},

We would like to request your best quote for the following components:

{lines_text}

Please provide for each line:
- Unit price (USD)
- Available quantity
- Lead time (days)
- Condition & certification

Reference: {vrfq.rfq_number}

Please reply to this email with your quotation at your earliest convenience.

Best regards"""


# ─────────────────────────────────────────────
# Phase 4c: Enter / Update Vendor Quote
# ─────────────────────────────────────────────

@login_required
def vendor_rfq_quote(request, pk):
    vrfq = get_object_or_404(VendorRFQ, pk=pk)
    lines = VendorRFQLine.objects.filter(
        vendor_rfq=vrfq
    ).prefetch_related('quotes').order_by('line_number')

    if not lines.exists():
        messages.warning(request, f'No lines found for {vrfq.rfq_number}. Add lines first.')
        return redirect('vendor_rfq_detail', pk=pk)

    if request.method == 'POST':
        any_saved = False

        for line in lines:
            unit_price = request.POST.get(f'price_{line.pk}', '').strip()
            qty_avail = request.POST.get(f'qty_{line.pk}', '').strip()
            lead_time = request.POST.get(f'lead_{line.pk}', '').strip()
            condition = request.POST.get(f'condition_{line.pk}', '').strip()
            cert = request.POST.get(f'cert_{line.pk}', '').strip()
            notes = request.POST.get(f'notes_{line.pk}', '').strip()

            # Skip if no price entered for this line
            if not unit_price:
                continue

            # Update existing quote or create new one
            quote, _ = VendorQuoteLine.objects.update_or_create(
                vendor_rfq_line=line,
                defaults={
                    'unit_price': unit_price,
                    'quantity_available': qty_avail or 0,
                    'lead_time_days': int(lead_time) if lead_time else None,
                    'condition': condition,
                    'certification': cert,
                    'notes': notes,
                    'source': VendorQuoteLine.SOURCE_MANUAL,
                    'entered_by': request.user,
                }
            )
            any_saved = True

        if any_saved:
            # Upgrade status to quoted if all lines now have a quote
            all_quoted = all(
                line.quotes.exists() for line in vrfq.lines.all()
            )
            vrfq.status = VendorRFQ.STATUS_QUOTED if all_quoted else vrfq.status
            vrfq.save()
            messages.success(request, 'Quote saved successfully.')
        else:
            messages.warning(request, 'No prices entered — nothing was saved.')

        return redirect('vendor_rfq_detail', pk=pk)

    return render(request, 'vendor_rfq/quote_entry.html', {
        'vrfq': vrfq,
        'lines': lines,
    })


# ─────────────────────────────────────────────
# Phase 5: Quote Comparison
# ─────────────────────────────────────────────

@login_required
def compare_quotes(request, inquiry_pk):
    inquiry = get_object_or_404(RFQ, pk=inquiry_pk)

    # Get only Vendor RFQs that have quotes
    vendor_rfq_qs = VendorRFQ.objects.filter(
        inquiry=inquiry
    ).annotate(
        has_quote=Exists(
            VendorQuoteLine.objects.filter(
                vendor_rfq_line__vendor_rfq=OuterRef('pk')
            )
        )
    ).filter(
        has_quote=True
    ).select_related(
        'vendor'
    ).prefetch_related(
        Prefetch(
            'lines',
            queryset=VendorRFQLine.objects.prefetch_related('quotes', 'inquiry_line')
        )
    )

    vendor_rfqs = list(vendor_rfq_qs)

    # POST → Confirm Winners
    if request.method == 'POST':

        winning_vrfq_line_ids = {
            int(val)
            for key, val in request.POST.items()
            if key.startswith('winner_') and val
        }

        if not winning_vrfq_line_ids:
            messages.warning(request, 'No winners selected.')
            return redirect('compare_quotes', inquiry_pk=inquiry.pk)

        with transaction.atomic():

            # Reset only pending lines
            VendorRFQLine.objects.filter(
                vendor_rfq__inquiry=inquiry,
                is_winner=False
            ).update(is_winner=False)

            winning_vendor_ids = set()

            for vrfq_line in VendorRFQLine.objects.select_related(
                'vendor_rfq',
                'inquiry_line'
            ).filter(
                pk__in=winning_vrfq_line_ids
            ):

                vrfq_line.is_winner = True
                vrfq_line.save(update_fields=['is_winner'])

                winning_vendor_ids.add(vrfq_line.vendor_rfq_id)

                # Mark competitors LOST for THIS SAME line
                VendorRFQ.objects.filter(
                    inquiry=inquiry,
                    lines__inquiry_line=vrfq_line.inquiry_line,
                    lines__quotes__isnull=False
                ).exclude(
                    pk=vrfq_line.vendor_rfq_id
                ).update(status=VendorRFQ.STATUS_LOST)

            # Mark winners WON
            VendorRFQ.objects.filter(
                pk__in=winning_vendor_ids
            ).update(status=VendorRFQ.STATUS_WON)

        messages.success(request, 'Winners confirmed successfully.')
        return redirect('rfq_detail', pk=inquiry_pk)

    # ONLY SHOW PENDING LINES (No Winner Yet)
    inquiry_lines = inquiry.lines.annotate(
        has_winner=Exists(
            VendorRFQLine.objects.filter(
                inquiry_line=OuterRef('pk'),
                is_winner=True
            )
        )
    ).filter(
        has_winner=False
    )

    # If no pending lines → redirect
    if not inquiry_lines.exists():
        messages.info(request, "All lines already finalized.")
        return redirect('rfq_detail', pk=inquiry_pk)

    # Build Comparison Grid
    grid = []

    for inq_line in inquiry_lines:

        row = {
            'inquiry_line': inq_line,
            'vendor_quotes': [],
            'best_price': None,
        }

        prices = []

        for vrfq in vendor_rfqs:

            vrfq_line = next(
                (line for line in vrfq.lines.all()
                 if line.inquiry_line_id == inq_line.id),
                None
            )

            best_quote = (
                vrfq_line.quotes.first()
                if vrfq_line and vrfq_line.quotes.exists()
                else None
            )

            if best_quote:
                prices.append(best_quote.unit_price)

            row['vendor_quotes'].append({
                'vrfq': vrfq,
                'vrfq_line': vrfq_line,
                'quote': best_quote,
            })

        if prices:
            row['best_price'] = min(prices)
            grid.append(row)

    return render(request, 'vendor_rfq/compare_quotes1.html', {
        'inquiry': inquiry,
        'vendor_rfqs': vendor_rfqs,
        'grid': grid,
    })


@login_required
def debug_inquiry(request, inquiry_pk):
    from django.http import HttpResponse
    from apps.vendor_rfq.models import VendorRFQ, VendorRFQLine, VendorQuoteLine

    inquiry = get_object_or_404(RFQ, pk=inquiry_pk)
    lines = []
    for vrfq in VendorRFQ.objects.filter(inquiry=inquiry):
        vrfq_lines = vrfq.lines.all()
        quote_count = VendorQuoteLine.objects.filter(vendor_rfq_line__vendor_rfq=vrfq).count()
        lines.append(
            f"VRFQ {vrfq.rfq_number} | {vrfq.vendor.name} | "
            f"status={vrfq.status} | lines={vrfq_lines.count()} | quotes={quote_count}"
        )
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@login_required
def verify_vendor_quote(request, parsed_quote_id):
    """User verifies AI-parsed vendor quote before saving as VendorQuoteLines."""
    from .models import ParsedVendorQuote

    parsed = get_object_or_404(
        ParsedVendorQuote.objects.select_related(
            'vendor_rfq__vendor', 'vendor_rfq__inquiry', 'email_log'
        ).prefetch_related('vendor_rfq__lines'),
        pk=parsed_quote_id
    )
    vrfq = parsed.vendor_rfq
    lines = vrfq.lines.prefetch_related('quotes').all()

    if request.method == 'POST':
        import json as json_lib
        action = request.POST.get('action')

        if action == 'confirm':
            quote_lines_json = request.POST.get('quote_lines_json', '[]')
            quote_lines = json_lib.loads(quote_lines_json)

            for item in quote_lines:
                vrfq_line_id = item.get('vrfq_line_id')
                unit_price = item.get('unit_price')
                if not vrfq_line_id or not unit_price:
                    continue

                try:
                    vrfq_line = VendorRFQLine.objects.get(pk=vrfq_line_id, vendor_rfq=vrfq)
                except VendorRFQLine.DoesNotExist:
                    continue

                VendorQuoteLine.objects.update_or_create(
                    vendor_rfq_line=vrfq_line,
                    defaults={
                        'unit_price': unit_price,
                        'quantity_available': item.get('qty_available', 0),
                        'lead_time_days': item.get('lead_time_days') or None,
                        'condition': item.get('condition', ''),
                        'certification': item.get('certification', ''),
                        'notes': item.get('notes', ''),
                        'source': VendorQuoteLine.SOURCE_EMAIL,
                        'entered_by': request.user,
                    }
                )

            # Mark confirmed
            parsed.is_confirmed = True
            parsed.confirmed_by = request.user
            parsed.confirmed_at = timezone.now()
            parsed.save()

            # Update VendorRFQ status
            all_quoted = all(line.quotes.exists() for line in vrfq.lines.all())
            if all_quoted:
                vrfq.status = VendorRFQ.STATUS_QUOTED
                vrfq.save()

            messages.success(request, f'Vendor quote confirmed for {vrfq.vendor.name}.')
            return redirect('vendor_rfq_detail', pk=vrfq.pk)

        elif action == 'skip':
            parsed.email_log.status = 'irrelevant'
            parsed.email_log.save()
            messages.info(request, 'Quote email dismissed.')
            return redirect('vendor_rfq_detail', pk=vrfq.pk)

    # Build initial data: match parsed lines to VendorRFQLines by PN
    initial_matches = []
    for parsed_line in parsed.raw_parsed.get('lines', []):
        pn = parsed_line.get('pn', '').strip()
        matched_line = lines.filter(part_number__iexact=pn).first()
        initial_matches.append({
            'parsed':  parsed_line,
            'matched': matched_line,
        })

    return render(request, 'vendor_rfq/verify_vendor_quote.html', {
        'parsed': parsed,
        'vrfq': vrfq,
        'lines': lines,
        'initial_matches': initial_matches,
    })


@login_required
def retry_parse_vendor_quote(request, parsed_quote_id):
    """Re-run AI parsing on a vendor quote email and redirect back to verify."""
    from apps.vendor_rfq.models import ParsedVendorQuote
    from apps.email_integration.parser import parse_vendor_quote_email

    parsed = get_object_or_404(ParsedVendorQuote, pk=parsed_quote_id)
    vrfq = parsed.vendor_rfq

    try:
        rfq_line_pns = list(vrfq.lines.values_list('part_number', flat=True))
        result = parse_vendor_quote_email(
            subject=parsed.email_log.subject,
            body_text=parsed.email_log.body_text,
            rfq_lines=rfq_line_pns,
        )
        parsed.raw_parsed = result
        parsed.is_confirmed = False
        parsed.save()

        line_count = len(result.get('lines', []))
        if line_count > 0:
            messages.success(request, f'Re-parsed successfully — {line_count} lines found.')
        else:
            messages.warning(request, 'Re-parsing completed but still no lines found. Edit manually below.')

    except Exception as e:
        messages.error(request, f'Parsing failed: {str(e)}')

    return redirect('verify_vendor_quote', parsed_quote_id=parsed_quote_id)
