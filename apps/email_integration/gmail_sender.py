# apps/email_integration/gmail_sender.py
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from .oauth import get_credentials_for_account


def send_email(account, to, subject, body):
    """Send a plain-text email via Gmail API using OAuth2."""
    creds   = get_credentials_for_account(account)
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body, 'plain')
    message['to']      = to
    message['from']    = account.email
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()