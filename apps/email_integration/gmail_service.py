import base64
from datetime import datetime, timezone
from googleapiclient.discovery import build
from .oauth import get_credentials_for_account
from .models import EmailLog


# def fetch_new_emails_for_account(account):
#     creds = get_credentials_for_account(account)
#     service = build('gmail', 'v1', credentials=creds)
#
#     results = service.users().messages().list(
#         userId='me',
#         q='in:inbox',
#         maxResults=50,
#     ).execute()
#
#     created_logs = []
#     for msg_ref in results.get('messages', []):
#         msg_id = msg_ref['id']
#         if EmailLog.objects.filter(gmail_message_id=msg_id).exists():
#             continue  # already imported — skip
#
#         msg = service.users().messages().get(
#             userId='me', id=msg_id, format='full'
#         ).execute()
#
#         log = _message_to_log(account, msg)
#         created_logs.append(log)
#
#     account.last_fetched_at = datetime.now(timezone.utc)
#     account.save(update_fields=['last_fetched_at'])
#     return created_logs


def _message_to_log(account, msg):
    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
    body_text = _extract_text(msg['payload'])

    return EmailLog.objects.create(
        account=account,
        direction='inbound',
        from_address=headers.get('From', ''),
        to_addresses=headers.get('To', ''),
        subject=headers.get('Subject', '(no subject)'),
        body_text=body_text,
        gmail_message_id=msg['id'],
        received_at=datetime.fromtimestamp(
            int(msg['internalDate']) / 1000, tz=timezone.utc
        ),
        status='received',
    )


def _extract_text(payload):
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')
    for part in payload.get('parts', []):
        result = _extract_text(part)
        if result:
            return result
    return ''


# apps/email_integration/gmail_service.py

def fetch_new_emails_for_account(account):
    creds   = get_credentials_for_account(account)
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(
        userId='me', q='in:inbox is:unread', maxResults=50
    ).execute()

    created_logs = []
    for msg_ref in results.get('messages', []):
        msg_id = msg_ref['id']
        if EmailLog.objects.filter(gmail_message_id=msg_id).exists():
            continue

        msg = service.users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()

        log = _message_to_log(account, msg)
        created_logs.append(log)

    account.last_fetched_at = datetime.now(timezone.utc)
    account.save(update_fields=['last_fetched_at'])
    return created_logs


def detect_vendor_rfq_reply(email_log):
    """
    Check if an inbound email is a vendor replying to one of our VendorRFQs.
    Matches on:
      1. In-Reply-To / References header matching our outbound email Message-ID
      2. VendorRFQ number (e.g. VRFQ-0001) mentioned in subject or body
      3. Sender email matching a vendor's email address
    Returns VendorRFQ instance or None.
    """
    from apps.vendor_rfq.models import VendorRFQ

    # Strategy 1: subject contains our VRFQ number
    import re
    subject = email_log.subject or ''
    body    = email_log.body_text or ''
    combined = f"{subject} {body}"

    match = re.search(r'VRFQ-\d+', combined, re.IGNORECASE)
    if match:
        vrfq_number = match.group().upper()
        vrfq = VendorRFQ.objects.filter(
            rfq_number=vrfq_number, status=VendorRFQ.STATUS_SENT
        ).first()
        if vrfq:
            return vrfq

    # Strategy 2: sender email matches a vendor who has a sent VendorRFQ
    sender = email_log.from_address or ''
    # Extract plain email from "Name <email>" format
    email_match = re.search(r'<(.+?)>', sender)
    sender_email = email_match.group(1) if email_match else sender

    from apps.companies.models import Contact

    contact = Contact.objects.filter(email__iexact=sender_email).first()
    if contact:
        vrfq = VendorRFQ.objects.filter(
            vendor=contact.company,
            status=VendorRFQ.STATUS_SENT,
        ).order_by('-sent_at').first()

    return vrfq  # None if not found