from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from django.conf import settings


def get_oauth2_flow(state=None):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_OAUTH2_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=settings.GOOGLE_OAUTH2_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.GOOGLE_OAUTH2_REDIRECT_URI
    return flow


def get_credentials_for_account(account):
    """Return valid Credentials, auto-refreshing if expired."""
    creds = Credentials(
        token=account.oauth2_access_token,
        refresh_token=account.oauth2_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        account.oauth2_access_token = creds.token
        account.oauth2_token_expiry = creds.expiry
        account.save(update_fields=['oauth2_access_token', 'oauth2_token_expiry'])
    return creds