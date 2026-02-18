import os

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import EmailAccount, EmailLog, ParsedEmailData
from .gmail_service import fetch_new_emails_for_account
from .parser import parse_email_with_ai


@login_required
def email_dashboard(request):
    accounts = EmailAccount.objects.filter(is_active=True)
    pending_review = EmailLog.objects.filter(
        status='parsed'
    ).select_related('account', 'parsed_data')[:20]
    recent_emails = EmailLog.objects.select_related('account').all()[:50]
    return render(request, 'email_integration/dashboard.html', {
        'accounts': accounts,
        'recent_emails': recent_emails,
        'pending_review': pending_review,
        'pending_count': pending_review.count(),
    })


@login_required
def fetch_emails_now(request):
    """Manual fetch triggered by the dashboard button."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    accounts = EmailAccount.objects.filter(is_active=True, use_oauth2=True)
    if not accounts.exists():
        return JsonResponse({
            'error': 'No Gmail accounts connected. Add one first.'
        }, status=400)

    total_fetched = 0
    total_parsed = 0
    total_irrelevant = 0
    errors = []

    for account in accounts:
        try:
            new_logs = fetch_new_emails_for_account(account)
            total_fetched += len(new_logs)

            for log in new_logs:
                # relevant, score, reason = is_email_relevant(log)
                # log.relevance_score = score
                # log.relevance_reason = reason
                #
                # if not relevant:
                #     log.status = 'irrelevant'
                #     log.save()
                #     total_irrelevant += 1
                #     continue

                # Parse relevant emails
                log.status = 'parsing'
                log.save()
                try:
                    result = parse_email_with_ai(log.subject, log.body_text)
                    ParsedEmailData.objects.update_or_create(
                        email_log=log,
                        defaults={
                            'raw_parsed': result,
                            'confirmed_lines': result.get('lines', []),
                        }
                    )
                    log.status = 'parsed'
                    log.save()
                    total_parsed += 1
                except Exception as e:
                    log.status = 'failed'
                    log.save()
                    errors.append(f"Parse error ({log.subject[:30]}): {str(e)}")

        except Exception as e:
            errors.append(f"{account.email}: {str(e)}")

    return JsonResponse({
        'fetched': total_fetched,
        'parsed': total_parsed,
        'irrelevant': total_irrelevant,
        'errors': errors,
    })


@login_required
def email_verify(request, email_log_id):
    """User reviews and confirms AI-parsed lines before creating RFQ."""
    import json
    email_log = get_object_or_404(EmailLog, id=email_log_id)
    parsed = get_object_or_404(ParsedEmailData, email_log=email_log)

    if request.method == 'POST':
        action = request.POST.get('action')
        lines_json = request.POST.get('lines_json', '[]')

        if action == 'confirm':
            lines = json.loads(lines_json)
            original = parsed.raw_parsed.get('lines', [])
            parsed.confirmed_lines = lines
            parsed.is_confirmed = True
            parsed.confirmed_by = request.user
            parsed.confirmed_at = timezone.now()
            parsed.corrections_made = (lines != original)
            parsed.save()

            email_log.status = 'confirmed'
            email_log.save()

            request.session['rfq_prefill'] = json.dumps({
                'lines': lines,
                'source': 'email_parsed',
                'subject': email_log.subject,
                'from': email_log.from_address,
            })
            messages.success(request, 'Email confirmed — pre-filling RFQ.')
            return redirect('/rfq/create/')

        elif action == 'skip':
            email_log.status = 'irrelevant'
            email_log.save()
            messages.info(request, 'Email marked as not relevant.')
            return redirect('email_dashboard')

    return render(request, 'email_integration/verify.html', {
        'email_log': email_log,
        'parsed': parsed,
    })


@login_required
def email_parse(request):
    """Manual paste-and-parse view (existing)."""
    if request.method == 'POST':
        body = request.POST.get('email_body', '')
        subject = request.POST.get('subject', '')
        result = parse_email_with_ai(subject, body)
        return JsonResponse({'parsed_lines': result.get('lines', []), 'subject': subject})
    return render(request, 'email_integration/parse.html')


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
    from .oauth import get_oauth2_flow
    flow = get_oauth2_flow()

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # dev only

    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    request.session['oauth2_state'] = state
    return redirect(auth_url)


@login_required
def oauth2_callback(request):
    from .oauth import get_oauth2_flow
    from googleapiclient.discovery import build

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # dev only

    state = request.session.get('oauth2_state')
    flow = get_oauth2_flow(state=state)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    creds = flow.credentials
    service = build('oauth2', 'v2', credentials=creds)
    user_info = service.userinfo().get().execute()
    account, created = EmailAccount.objects.update_or_create(
        email=user_info['email'],
        defaults={
            'name': user_info.get('name', user_info['email']),
            'use_oauth2': True,
            'oauth2_access_token': creds.token,
            'oauth2_refresh_token': creds.refresh_token or '',
            'oauth2_token_expiry': creds.expiry,
            'is_active': True,
        }
    )
    messages.success(request, f'Gmail {"connected" if created else "updated"}: {account.email}')
    return redirect('email_dashboard')