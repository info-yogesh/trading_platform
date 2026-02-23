# apps/email_integration/views.py
import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import EmailAccount, EmailLog, ParsedEmailData
from .gmail_service import fetch_new_emails_for_account
from .parser import parse_email_with_ai, parse_vendor_quote_email, classify_email
from ..rfq.models import RFQLine, RFQ
from ..vendor_rfq.models import VendorRFQ

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def email_dashboard(request):
    """
    Main email integration page.
    Optional GET param ?account=<id> scopes the Email Log to one account.
    """
    accounts = EmailAccount.objects.filter(is_active=True).order_by('name')

    active_account_id = None
    raw = request.GET.get('account')
    if raw:
        try:
            active_account_id = int(raw)
        except (ValueError, TypeError):
            pass

    # ── Inquiries: new inbound emails awaiting review ─────────────────────────
    inquiries = (
        EmailLog.objects
        .filter(
            direction='inbound',
            email_type='new_inquiry',
            status__in=['parsed', 'parse_failed'],
        )
        .select_related('account', 'parsed_data')
        .order_by('-received_at')[:30]
    )

    # ── Vendor RFQs: vendor replied to our outbound VRFQ ─────────────────────
    vendor_rfqs = (
        EmailLog.objects
        .filter(
            direction='inbound',
            email_type='vendor_reply',
            status__in=['parsed', 'parse_failed'],
        )
        .select_related('account', 'parsed_data', 'parsed_rfq', 'linked_inquiry')
        .order_by('-received_at')[:20]
    )

    # ── Email Log (optionally filtered) ──────────────────────────────────────
    log_qs = (
        EmailLog.objects
        .select_related('account', 'parsed_rfq', 'linked_inquiry')
        .order_by('-received_at')
    )
    if active_account_id:
        log_qs = log_qs.filter(account_id=active_account_id)
    recent_emails = log_qs[:60]

    return render(request, 'email_integration/dashboard.html', {
        'accounts': accounts,
        'active_account_id': active_account_id,
        'inquiries': inquiries,
        'inquiries_count': inquiries.count(),
        'vendor_rfqs': vendor_rfqs,
        'vendor_rfqs_count': vendor_rfqs.count(),
        'recent_emails': recent_emails,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Fetch
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def fetch_emails_now(request):
    """Fetch all active OAuth2 accounts."""
    return _run_fetch(EmailAccount.objects.filter(is_active=True, use_oauth2=True))


@login_required
@require_POST
def fetch_account_emails(request, account_id):
    """Fetch a single account (per-account Sync button)."""
    account = get_object_or_404(EmailAccount, pk=account_id, is_active=True)
    if not account.use_oauth2:
        return JsonResponse(
            {'error': f'Account "{account.name}" is not configured for Gmail OAuth2.'},
            status=400,
        )
    return _run_fetch(EmailAccount.objects.filter(pk=account.pk))


def _run_fetch(accounts_qs, use_paid_model=False):
    if not accounts_qs.exists():
        return JsonResponse(
            {'error': 'No active Gmail accounts found.'},
            status=400
        )

    total_fetched = 0
    total_parsed = 0
    total_failed = 0
    errors = []

    for account in accounts_qs:
        try:
            new_logs = fetch_new_emails_for_account(account)
            total_fetched += len(new_logs)

            for log in new_logs:
                log.status = 'parsing'
                log.save(update_fields=['status'])

                try:
                    subject = log.subject
                    body = log.body_text

                    # -------------------------
                    # Step 1: Classify Email
                    # -------------------------
                    email_type = classify_email(
                        subject, body
                    )

                    result = {"lines": []}

                    # -------------------------
                    # Step 2: Process by Type
                    # -------------------------

                    if email_type == "new_inquiry":

                        result = parse_email_with_ai(
                            subject,
                            body,
                        )

                        lines = result.get('lines', [])

                        ParsedEmailData.objects.update_or_create(
                            email_log=log,
                            defaults={
                                'raw_parsed': result,
                                'confirmed_lines': lines,
                            },
                        )

                    else:
                        # -------------------------
                        # Vendor Response
                        # -------------------------

                        rfq_number = None

                        if " (RFQ Number: " in subject:
                            try:
                                rfq_number = (
                                    subject.split(" (RFQ Number: ")[-1]
                                    .replace(")", "")
                                    .strip()
                                )
                            except Exception:
                                rfq_number = None

                        if rfq_number:
                            rfq = VendorRFQ.objects.filter(
                                rfq_number__icontains=rfq_number
                            ).first().inquiry

                            if rfq:
                                rfq_lines_qs = RFQLine.objects.filter(rfq=rfq)

                                rfq_lines = [
                                    line.part_number_raw or
                                    (line.part.part_number if line.part else "")
                                    for line in rfq_lines_qs
                                ]

                                rfq_lines = [pn for pn in rfq_lines if pn]

                                result = parse_vendor_quote_email(
                                    subject,
                                    body,
                                    rfq_lines=rfq_lines,
                                )

                                # -------------------------
                                # Step 3: Save Parsed Data
                                # -------------------------

                                lines = result.get('lines', [])
                                normalized_lines = []

                                for l in result.get("lines", []):
                                    normalized_lines.append({
                                        "pn": l.get("pn", ""),
                                        "description": l.get("notes", ""),  # optional mapping
                                        "qty": l.get("qty_available", ""),  # <-- fix
                                        "cd": l.get("condition", ""),  # <-- fix
                                        "unit_price": l.get("unit_price", ""),
                                        "lead_time": l.get("lead_time_days", ""),  # <-- fix
                                    })

                                ParsedEmailData.objects.update_or_create(
                                    email_log=log,
                                    defaults={
                                        "raw_parsed": result,
                                        "confirmed_lines": normalized_lines,
                                    },
                                )
                            else:
                                errors.append(
                                    f"RFQ not found: {rfq_number}"
                                )
                        else:
                            errors.append(
                                f"RFQ number missing in subject: {subject[:50]}"
                            )



                    # -------------------------
                    # Step 4: Update Status
                    # -------------------------

                    if lines:
                        log.status = 'parsed'
                        total_parsed += 1
                    else:
                        log.status = 'parse_failed'
                        total_failed += 1

                    log.save(update_fields=['status'])

                except Exception as exc:
                    print(exc)
                    log.status = 'parse_failed'
                    log.save(update_fields=['status'])
                    total_failed += 1
                    errors.append(
                        f"Parse error ({(log.subject or '')[:30]}): {str(exc)}"
                    )

        except Exception as exc:
            print(exc)
            errors.append(f"{account.email}: {str(exc)}")

    return JsonResponse({
        'fetched': total_fetched,
        'parsed': total_parsed,
        'parse_failed': total_failed,
        'errors': errors,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Review / Verify
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def email_verify(request, email_log_id):
    """
    Unified review page for:
      - new_inquiry  : fresh customer email → create Inquiry/RFQ
      - rfq_reply    : customer replied to our quote → show original inquiry alongside
      - vendor_reply : vendor replied to our VRFQ    → show original VRFQ alongside

    Also handles:
      - Manual line entry when AI parsing failed (status='parse_failed')
      - AI parse retry (AJAX endpoint below)
    """
    email_log = get_object_or_404(
        EmailLog.objects.select_related(
            'account', 'parsed_rfq', 'linked_inquiry',
            'linked_inquiry__parsed_rfq',
        ),
        id=email_log_id,
    )
    parsed = getattr(email_log, 'parsed_data', None)

    # Fetch the original inquiry/email this is replying to (if applicable)
    original_email = None
    original_lines = []
    if email_log.linked_inquiry:
        original_email = email_log.linked_inquiry
        orig_parsed = getattr(original_email, 'parsed_data', None)
        if orig_parsed:
            original_lines = orig_parsed.confirmed_lines or orig_parsed.raw_parsed.get('lines', [])

    # All replies that share the same thread as this email (for context)
    thread_emails = []
    if email_log.linked_inquiry:
        thread_emails = (
            EmailLog.objects
            .filter(linked_inquiry=email_log.linked_inquiry)
            .exclude(pk=email_log.pk)
            .order_by('received_at')
            .select_related('parsed_data')[:10]
        )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirm':
            lines_json = request.POST.get('lines_json', '[]')
            try:
                lines = json.loads(lines_json)
            except json.JSONDecodeError:
                lines = []

            manually_entered = request.POST.get('manually_entered', 'false') == 'true'

            # Ensure ParsedEmailData exists (may not if parsing completely failed)
            if parsed is None:
                parsed = ParsedEmailData(email_log=email_log, raw_parsed={'lines': []})

            original_ai_lines = parsed.raw_parsed.get('lines', [])
            parsed.confirmed_lines = lines
            parsed.is_confirmed = True
            parsed.confirmed_by = request.user
            parsed.confirmed_at = timezone.now()
            parsed.corrections_made = (lines != original_ai_lines)
            parsed.manually_entered = manually_entered
            parsed.save()

            email_log.status = 'confirmed'
            email_log.processed_at = timezone.now()
            email_log.save(update_fields=['status', 'processed_at'])

            # Pre-fill session so RFQ create view can consume it
            request.session['rfq_prefill'] = json.dumps({
                'lines': lines,
                'source': 'email_parsed',
                'subject': email_log.subject,
                'from': email_log.from_address,
                'email_log_id': email_log.id,
                'email_type': email_log.email_type,
                'manually_entered': manually_entered,
            })

            messages.success(request, 'Email confirmed — pre-filling Inquiry.')
            return redirect('/rfq/create/')

        elif action == 'skip':
            email_log.status = 'irrelevant'
            email_log.save(update_fields=['status'])
            messages.info(request, 'Email marked as not relevant.')
            return redirect('email_dashboard')

        elif action == 'reclassify':
            # Manual override of email_type
            new_type = request.POST.get('email_type')
            if new_type in dict(EmailLog.EMAIL_TYPE_CHOICES):
                email_log.email_type = new_type
                email_log.save(update_fields=['email_type'])
                messages.success(request, f'Email reclassified as: {email_log.get_email_type_display()}')
            return redirect('email_verify', email_log_id=email_log_id)

    return render(request, 'email_integration/verify.html', {
        'email_log': email_log,
        'parsed': parsed,
        'original_email': original_email,
        'original_lines': original_lines,
        'thread_emails': thread_emails,
        'email_type_choices': EmailLog.EMAIL_TYPE_CHOICES,
        'ai_failed': email_log.status == 'parse_failed',
        'has_lines': bool(parsed and (
            parsed.raw_parsed.get('lines') or parsed.confirmed_lines
        )),
    })


# ─────────────────────────────────────────────────────────────────────────────
# AJAX: Retry AI parse
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def retrigger_parse(request, email_log_id):
    """
    AJAX endpoint: re-run AI parsing on an email that previously failed.
    Updates ParsedEmailData and EmailLog.status.
    Returns JSON { lines: [...], status: 'parsed'|'parse_failed', error? }
    """
    email_log = get_object_or_404(EmailLog, id=email_log_id)
    errors= []
    try:
        if email_log.email_type in ["rfq_reply", "vendor_reply"]:
            subject = email_log.subject
            body = email_log.body_text
            rfq_number = None

            if " (RFQ Number: " in subject:
                try:
                    rfq_number = (
                        subject.split(" (RFQ Number: ")[-1]
                        .replace(")", "")
                        .strip()
                    )
                except Exception:
                    rfq_number = None

            if rfq_number:
                rfq = VendorRFQ.objects.filter(
                    rfq_number__icontains=rfq_number
                ).first().inquiry

                if rfq:
                    rfq_lines_qs = RFQLine.objects.filter(rfq=rfq)

                    rfq_lines = [
                        line.part_number_raw or
                        (line.part.part_number if line.part else "")
                        for line in rfq_lines_qs
                    ]

                    rfq_lines = [pn for pn in rfq_lines if pn]

                    result = parse_vendor_quote_email(
                        subject,
                        body,
                        rfq_lines=rfq_lines,
                    )

                    lines = result.get('lines', [])
                    normalized_lines = []

                    for l in result.get("lines", []):
                        normalized_lines.append({
                            "pn": l.get("pn", ""),
                            "description": l.get("notes", ""),  # optional mapping
                            "qty": l.get("qty_available", ""),  # <-- fix
                            "cd": l.get("condition", ""),  # <-- fix
                            "unit_price": l.get("unit_price", ""),
                            "lead_time": l.get("lead_time_days", ""),  # <-- fix
                        })

                    ParsedEmailData.objects.update_or_create(
                        email_log=email_log,
                        defaults={
                            "raw_parsed": result,
                            "confirmed_lines": normalized_lines,
                        },
                    )
                    new_status = 'parsed' if lines else 'parse_failed'
                    email_log.status = new_status
                    email_log.save(update_fields=['status'])
                    response = {'lines': normalized_lines, 'status': new_status}
                    print(response)
                    return JsonResponse(response)
                else:
                    errors.append(
                        f"RFQ not found: {rfq_number}"
                    )
            else:
                errors.append(
                    f"RFQ number missing in subject: {subject[:50]}"
                )

        else:
            subject = email_log.subject
            body = email_log.body_text

            result = parse_email_with_ai(
                subject,
                body,
            )

            lines = result.get('lines', [])

            ParsedEmailData.objects.update_or_create(
                email_log=email_log,
                defaults={
                    'raw_parsed': result,
                    'confirmed_lines': lines,
                },
            )
            new_status = 'parsed' if lines else 'parse_failed'
            email_log.status = new_status
            email_log.save(update_fields=['status'])
            response = {'lines': lines, 'status': new_status}
            print(response)
            return JsonResponse(response)

    except Exception as exc:
        print(exc)
        return JsonResponse({'lines': [], 'status': 'parse_failed', 'error': str(exc), "errors": errors}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# AJAX: Reclassify email type
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def reclassify_email(request, email_log_id):
    """
    AJAX endpoint: manually override the AI classification of an email.
    Body: { email_type: 'new_inquiry' | 'rfq_reply' | 'vendor_reply' | 'other' }
    """
    email_log = get_object_or_404(EmailLog, id=email_log_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    new_type = data.get('email_type', '')
    valid_types = [t[0] for t in EmailLog.EMAIL_TYPE_CHOICES]
    if new_type not in valid_types:
        return JsonResponse({'error': f'Invalid type: {new_type}'}, status=400)

    email_log.email_type = new_type
    email_log.save(update_fields=['email_type'])
    return JsonResponse({'email_type': new_type, 'display': email_log.get_email_type_display()})


# ─────────────────────────────────────────────────────────────────────────────
# Manual parse (paste-and-parse)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def email_parse(request):
    if request.method == 'POST':
        body = request.POST.get('email_body', '')
        subject = request.POST.get('subject', '')
        result = parse_email_with_ai(subject, body)
        return JsonResponse({'parsed_lines': result.get('lines', []), 'subject': subject})
    return render(request, 'email_integration/parse.html')


# ─────────────────────────────────────────────────────────────────────────────
# Account management
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def email_account_create(request):
    if request.method == 'POST':
        EmailAccount.objects.create(
            name=request.POST['name'],
            email=request.POST['email'],
            imap_host=request.POST.get('imap_host', ''),
            imap_port=request.POST.get('imap_port', 993),
            smtp_host=request.POST.get('smtp_host', ''),
            smtp_port=request.POST.get('smtp_port', 587),
            use_tls=request.POST.get('use_tls') == 'on',
        )
        messages.success(request, 'Email account configured.')
        return redirect('email_dashboard')
    return render(request, 'email_integration/account_form.html')


@login_required
def oauth2_start(request):
    from .gmail_service import get_oauth2_auth_url
    account_id = request.GET.get('account_id')
    auth_url = get_oauth2_auth_url(account_id)
    return redirect(auth_url)


@login_required
def oauth2_callback(request):
    from .gmail_service import handle_oauth2_callback
    code = request.GET.get('code')
    state = request.GET.get('state')
    handle_oauth2_callback(code, state)
    messages.success(request, 'Gmail account connected successfully.')
    return redirect('email_dashboard')