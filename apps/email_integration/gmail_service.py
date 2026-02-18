import base64
from datetime import datetime, timezone
from googleapiclient.discovery import build
from .oauth import get_credentials_for_account
from .models import EmailLog


def fetch_new_emails_for_account(account):
    creds = get_credentials_for_account(account)
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(
        userId='me',
        q='in:inbox',
        maxResults=50,
    ).execute()

    created_logs = []
    for msg_ref in results.get('messages', []):
        msg_id = msg_ref['id']
        if EmailLog.objects.filter(gmail_message_id=msg_id).exists():
            continue  # already imported — skip

        msg = service.users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()

        log = _message_to_log(account, msg)
        created_logs.append(log)

    account.last_fetched_at = datetime.now(timezone.utc)
    account.save(update_fields=['last_fetched_at'])
    return created_logs


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