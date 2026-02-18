# import logging
# from celery import shared_task
# from django.utils import timezone
# from .models import EmailAccount, EmailLog
# from .gmail_service import fetch_new_emails_for_account
# from .parser import is_email_relevant, parse_email_with_ai
#
# logger = logging.getLogger(__name__)
#
#
# @shared_task
# def fetch_all_accounts():
#     """Triggered every 5 minutes by Celery Beat."""
#     accounts = EmailAccount.objects.filter(is_active=True, use_oauth2=True)
#     for account in accounts:
#         fetch_account_emails.delay(account.id)
#
#
# @shared_task
# def fetch_account_emails(account_id):
#     """Fetch new emails for one account, filter relevance, trigger parsing."""
#     try:
#         account = EmailAccount.objects.get(id=account_id)
#         new_emails = fetch_new_emails_for_account(account)  # see gmail_service.py
#         logger.info(f"Fetched {len(new_emails)} new emails for {account.email}")
#         for email_log in new_emails:
#             check_and_parse_email.delay(email_log.id)
#     except Exception as e:
#         logger.error(f"Fetch failed for account {account_id}: {e}")
#
#
# @shared_task
# def check_and_parse_email(email_log_id):
#     """Check relevance, then parse if relevant."""
#     try:
#         email_log = EmailLog.objects.get(id=email_log_id)
#         relevant, score, reason = is_email_relevant(email_log)
#         email_log.relevance_score = score
#         email_log.relevance_reason = reason
#
#         if not relevant:
#             email_log.status = 'irrelevant'
#             email_log.save()
#             return
#
#         email_log.status = 'parsing'
#         email_log.save()
#
#         parsed_lines = parse_email_with_ai(email_log.subject, email_log.body_text)
#         from .models import ParsedEmailData
#         ParsedEmailData.objects.update_or_create(
#             email_log=email_log,
#             defaults={'raw_parsed': parsed_lines, 'confirmed_lines': parsed_lines}
#         )
#         email_log.status = 'parsed'
#         email_log.save()
#     except Exception as e:
#         logger.error(f"Parse failed for email_log {email_log_id}: {e}")
#         EmailLog.objects.filter(id=email_log_id).update(status='failed')