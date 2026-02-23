# # apps/email_integration/classifier.py
# """
# Email classifier — determines the type of every inbound email.
#
# Classification logic (in order of precedence):
# ─────────────────────────────────────────────────────────────────────────────
# 1. THREAD MATCH (strongest signal):
#    - Check `In-Reply-To` header against `message_id_header` of all known
#      EmailLog records.
#    - If the matched parent is outbound (direction='outbound') → vendor_reply
#    - If the matched parent is inbound  (direction='inbound')  → rfq_reply
#    - Walk the References chain if In-Reply-To alone doesn't match.
#
# 2. GMAIL THREAD ID MATCH:
#    - If gmail_thread_id matches an existing EmailLog, use that thread's
#      email_type as context.
#
# 3. SUBJECT PREFIX MATCH:
#    - Subject starts with "Re:" or "RE:" → likely a reply
#    - Look for a matching outbound email with a similar subject.
#
# 4. RFQ NUMBER IN BODY/SUBJECT:
#    - Scan body + subject for known RFQ numbers (e.g. RFQ-20260223-0001).
#    - If found and matches an existing RFQ, it's an rfq_reply.
#
# 5. DEFAULT:
#    - If inbound and none of the above → new_inquiry.
#    - If irrelevant signals → other.
# ─────────────────────────────────────────────────────────────────────────────
# """
#
# import re
# import logging
#
# from django.db.models import Q
#
# logger = logging.getLogger(__name__)
#
#
# def classify_email(email_log):
#     """
#     Classify a single EmailLog record and set its email_type and linked_inquiry.
#
#     Must be called AFTER the email is saved so it has a PK and the header
#     fields (in_reply_to, references_header, gmail_thread_id) are populated.
#
#     Returns the updated email_log (caller must save()).
#     """
#     from .models import EmailLog  # local import to avoid circular at module level
#
#     if email_log.direction != 'inbound':
#         # Outbound emails are not classified by this function
#         return email_log
#
#     # ── 1. In-Reply-To header match ───────────────────────────────────────────
#     if email_log.in_reply_to:
#         parent = _find_by_message_id(email_log.in_reply_to)
#         if parent:
#             email_log.linked_inquiry = parent
#             email_log.email_type = _reply_type_from_parent(parent)
#             logger.debug(
#                 "classify_email(%d): In-Reply-To match → %s (parent %d)",
#                 email_log.pk, email_log.email_type, parent.pk,
#             )
#             return email_log
#
#     # ── 2. References chain walk ───────────────────────────────────────────────
#     if email_log.references_header:
#         # References is newest-first or oldest-first depending on client;
#         # we try all of them and pick the most informative match.
#         ref_ids = email_log.references_header.split()
#         for ref_id in reversed(ref_ids):   # prefer newest in chain
#             parent = _find_by_message_id(ref_id.strip())
#             if parent:
#                 email_log.linked_inquiry = _find_thread_root(parent)
#                 email_log.email_type = _reply_type_from_parent(parent)
#                 logger.debug(
#                     "classify_email(%d): References match → %s (ref %s)",
#                     email_log.pk, email_log.email_type, ref_id,
#                 )
#                 return email_log
#
#     # ── 3. Gmail thread ID match ──────────────────────────────────────────────
#     if email_log.gmail_thread_id:
#         thread_sibling = (
#             EmailLog.objects
#             .filter(gmail_thread_id=email_log.gmail_thread_id)
#             .exclude(pk=email_log.pk)
#             .order_by('received_at')
#             .first()
#         )
#         if thread_sibling:
#             root = _find_thread_root(thread_sibling)
#             email_log.linked_inquiry = root
#             email_log.email_type = _reply_type_from_parent(thread_sibling)
#             logger.debug(
#                 "classify_email(%d): Thread-ID match → %s (sibling %d)",
#                 email_log.pk, email_log.email_type, thread_sibling.pk,
#             )
#             return email_log
#
#     # ── 4. Subject "Re:" + subject matching ───────────────────────────────────
#     clean_subject = _strip_reply_prefix(email_log.subject)
#     if clean_subject != email_log.subject:
#         # Subject has a Re: prefix — search for matching outbound
#         outbound_match = (
#             EmailLog.objects
#             .filter(
#                 direction='outbound',
#                 subject__icontains=clean_subject[:60],   # first 60 chars
#             )
#             .order_by('-received_at')
#             .first()
#         )
#         if outbound_match:
#             email_log.linked_inquiry = _find_thread_root(outbound_match)
#             email_log.email_type = 'vendor_reply'
#             logger.debug(
#                 "classify_email(%d): Re: subject match → vendor_reply",
#                 email_log.pk,
#             )
#             return email_log
#
#         # Also check for inbound inquiry with matching subject
#         inbound_match = (
#             EmailLog.objects
#             .filter(
#                 direction='inbound',
#                 email_type='new_inquiry',
#                 subject__icontains=clean_subject[:60],
#             )
#             .exclude(pk=email_log.pk)
#             .order_by('-received_at')
#             .first()
#         )
#         if inbound_match:
#             email_log.linked_inquiry = inbound_match
#             email_log.email_type = 'rfq_reply'
#             logger.debug(
#                 "classify_email(%d): Re: inbound subject match → rfq_reply",
#                 email_log.pk,
#             )
#             return email_log
#
#     # ── 5. RFQ number in body/subject ─────────────────────────────────────────
#     rfq_number = _extract_rfq_number(email_log.subject + ' ' + email_log.body_text[:2000])
#     if rfq_number:
#         from apps.rfq.models import RFQ
#         try:
#             rfq = RFQ.objects.get(rfq_number=rfq_number)
#             # Find the email that originally generated this RFQ
#             origin_email = (
#                 EmailLog.objects
#                 .filter(parsed_rfq=rfq)
#                 .order_by('received_at')
#                 .first()
#             )
#             email_log.parsed_rfq = rfq
#             email_log.linked_inquiry = origin_email
#             email_log.email_type = 'rfq_reply'
#             logger.debug(
#                 "classify_email(%d): RFQ# body match → rfq_reply (%s)",
#                 email_log.pk, rfq_number,
#             )
#             return email_log
#         except RFQ.DoesNotExist:
#             pass
#
#     # ── Default: treat as new inquiry ─────────────────────────────────────────
#     email_log.email_type = 'new_inquiry'
#     logger.debug("classify_email(%d): default → new_inquiry", email_log.pk)
#     return email_log
#
#
# # ─────────────────────────────────────────────────────────────────────────────
# # Helpers
# # ─────────────────────────────────────────────────────────────────────────────
#
# def _find_by_message_id(msg_id: str):
#     """Look up an EmailLog by its message_id_header. Returns None if not found."""
#     from .models import EmailLog
#     # Strip angle brackets if present
#     clean = msg_id.strip().strip('<>').strip()
#     if not clean:
#         return None
#     return (
#         EmailLog.objects
#         .filter(Q(message_id_header=msg_id) | Q(message_id_header=f'<{clean}>'))
#         .first()
#     )
#
#
# def _find_thread_root(email_log):
#     """
#     Walk linked_inquiry chain upward to find the very first email in the thread.
#     Prevents infinite loops with a depth limit.
#     """
#     visited = set()
#     current = email_log
#     depth = 0
#     while current.linked_inquiry_id and depth < 10:
#         if current.linked_inquiry_id in visited:
#             break
#         visited.add(current.pk)
#         current = current.linked_inquiry
#         depth += 1
#     return current
#
#
# def _reply_type_from_parent(parent_email_log):
#     """
#     Decide the email_type for a new email based on what its parent was.
#     - Parent is outbound → we sent it → vendor_reply
#     - Parent is inbound  → they started the thread → rfq_reply
#     """
#     if parent_email_log.direction == 'outbound':
#         return 'vendor_reply'
#     return 'rfq_reply'
#
#
# def _strip_reply_prefix(subject: str) -> str:
#     """Remove leading Re: / RE: / Fwd: etc. from a subject line."""
#     return re.sub(r'^(Re|RE|Fwd|FW|AW|SV)\s*:\s*', '', subject, flags=re.IGNORECASE).strip()
#
#
# def _extract_rfq_number(text: str):
#     """
#     Look for an RFQ number pattern like RFQ-20260223-0001 in the given text.
#     Returns the first match or None.
#     """
#     m = re.search(r'\bRFQ-\d{8}-\d{4}\b', text)
#     return m.group(0) if m else None