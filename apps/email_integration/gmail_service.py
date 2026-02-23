# apps/email_integration/gmail_service.py
"""
Gmail fetcher — pulls new messages, stores headers needed for thread detection,
then calls the classifier to set email_type / linked_inquiry.
"""
import base64
import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build

from .oauth import get_credentials_for_account
from .models import EmailLog

logger = logging.getLogger(__name__)


def fetch_new_emails_for_account(account):
    """
    Fetch all new inbox messages for the given account.
    Returns a list of newly-created EmailLog records.
    """
    creds = get_credentials_for_account(account)
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(
        userId='me',
        q='in:inbox',
        maxResults=50,
    ).execute()

    created_logs = []
    for msg_ref in results.get('messages', []):
        gmail_msg_id = msg_ref['id']
        if EmailLog.objects.filter(gmail_message_id=gmail_msg_id).exists():
            continue  # dedup — already imported

        msg = service.users().messages().get(
            userId='me', id=gmail_msg_id, format='full'
        ).execute()

        log = _message_to_log(account, msg)
        if log:
            created_logs.append(log)

    account.last_fetched_at = datetime.now(timezone.utc)
    account.save(update_fields=['last_fetched_at'])
    logger.info("Fetched %d new emails for %s", len(created_logs), account.email)
    return created_logs


def _message_to_log(account, msg):
    """
    Convert a raw Gmail API message object to an EmailLog record.
    Captures all RFC 2822 headers needed for thread-reply detection.
    Also calls the classifier immediately after save.
    """
    from .classifier import classify_email  # local import to avoid circular

    headers_list = msg['payload'].get('headers', [])
    headers = {h['name']: h['value'] for h in headers_list}

    body_text = _extract_text(msg['payload'])
    has_attachments = _has_attachments(msg['payload'])
    thread_id = msg.get('threadId', '')

    try:
        log = EmailLog.objects.create(
            account=account,
            direction='inbound',
            # ── RFC 2822 / thread fields ──────────────────────────────────────
            from_address=headers.get('From', ''),
            to_addresses=headers.get('To', ''),
            subject=headers.get('Subject', '(no subject)'),
            message_id_header=headers.get('Message-ID', ''),
            in_reply_to=headers.get('In-Reply-To', ''),
            references_header=headers.get('References', ''),
            gmail_thread_id=thread_id,
            # ── content ──────────────────────────────────────────────────────
            body_text=body_text,
            has_attachments=has_attachments,
            gmail_message_id=msg['id'],
            received_at=datetime.fromtimestamp(
                int(msg['internalDate']) / 1000, tz=timezone.utc
            ),
            status='received',
            email_type='other',  # will be updated by classifier below
        )
    except Exception as exc:
        logger.error("Failed to create EmailLog for gmail_id=%s: %s", msg['id'], exc)
        return None

    # ── Classify: new_inquiry vs rfq_reply vs vendor_reply ───────────────────
    try:
        classify_email(log)
        log.save(update_fields=[
            'email_type', 'linked_inquiry', 'parsed_rfq',
        ])
    except Exception as exc:
        logger.warning("Classification failed for EmailLog %d: %s", log.pk, exc)
        log.email_type = 'new_inquiry'
        log.save(update_fields=['email_type'])

    return log


# ─────────────────────────────────────────────────────────────────────────────
# Body extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(payload, _depth=0):
    """Recursively extract plain-text body from a Gmail message payload."""
    if _depth > 10:
        return ''

    mime = payload.get('mimeType', '')

    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')

    if mime == 'text/html' and not payload.get('parts'):
        # Fallback: use HTML only if no plain-text version exists
        data = payload.get('body', {}).get('data', '')
        if data:
            raw_html = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')
            # Strip tags crudely for plain-text display
            import re
            return re.sub(r'<[^>]+>', ' ', raw_html)

    # Walk parts — prefer plain-text parts
    plain_parts = []
    for part in payload.get('parts', []):
        result = _extract_text(part, _depth + 1)
        if result:
            plain_parts.append(result)

    return '\n'.join(plain_parts)


def _has_attachments(payload, _depth=0):
    """Return True if the message has any non-inline attachments."""
    if _depth > 10:
        return False
    for part in payload.get('parts', []):
        disposition = ''
        for h in part.get('headers', []):
            if h['name'].lower() == 'content-disposition':
                disposition = h['value'].lower()
        if 'attachment' in disposition:
            return True
        if _has_attachments(part, _depth + 1):
            return True
    return False