"""
Management command to seed complete dummy data for testing the full
email → parse → inquiry → vendor RFQ → quote → compare flow.

Usage:
    python manage.py seed_test_flow
    python manage.py seed_test_flow --reset   # wipe and reseed
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Seed dummy data to test the full email-to-quote flow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete existing seed data before creating new'
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('🗑  Resetting seed data...')
            self._reset()

        self.stdout.write(self.style.SUCCESS('\n🌱 Seeding test data...\n'))

        user     = self._get_or_create_user()
        vendors  = self._seed_vendors()
        customer = self._seed_customer()
        parts    = self._seed_parts(user)
        account  = self._seed_email_account()
        email_log, parsed = self._seed_customer_inquiry_email(account)
        inquiry  = self._seed_inquiry(customer, user)
        vrfqs    = self._seed_vendor_rfqs(inquiry, vendors, user)
        pq       = self._seed_vendor_quote_email(account, vrfqs, user)

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete!\n'))
        self.stdout.write('─' * 60)
        self.stdout.write('🔗 Test URLs:')
        self.stdout.write(f'  Email Dashboard    → http://127.0.0.1:8000/email/')
        self.stdout.write(f'  Verify Inquiry     → http://127.0.0.1:8000/email/verify/{email_log.pk}/')
        self.stdout.write(f'  Inquiry Detail     → http://127.0.0.1:8000/rfq/{inquiry.pk}/')
        self.stdout.write(f'  Send to Vendors    → http://127.0.0.1:8000/vendor-rfq/inquiry/{inquiry.pk}/send-to-vendors/')
        for vrfq in vrfqs:
            self.stdout.write(f'  {vrfq.vendor.name:<20} → http://127.0.0.1:8000/vendor-rfq/{vrfq.pk}/')
        if pq:
            self.stdout.write(f'  Verify Arrow Quote → http://127.0.0.1:8000/vendor-rfq/verify-quote/{pq.pk}/')
        self.stdout.write(f'  Compare Quotes     → http://127.0.0.1:8000/vendor-rfq/inquiry/{inquiry.pk}/compare/')
        self.stdout.write('─' * 60)

    # ─────────────────────────────────────────────
    def _reset(self):
        from apps.vendor_rfq.models import VendorRFQ, VendorRFQLine, VendorQuoteLine, ParsedVendorQuote
        from apps.email_integration.models import EmailLog, ParsedEmailData
        from apps.rfq.models import RFQ, RFQLine

        ParsedVendorQuote.objects.all().delete()
        VendorQuoteLine.objects.all().delete()
        VendorRFQLine.objects.all().delete()
        VendorRFQ.objects.all().delete()
        RFQLine.objects.filter(rfq__source='email').delete()
        RFQ.objects.filter(source='email').delete()
        ParsedEmailData.objects.all().delete()
        EmailLog.objects.filter(
            gmail_message_id__in=['seed_inquiry_001', 'seed_arrow_reply_001']
        ).delete()
        self.stdout.write('   Reset complete.\n')

    # ─────────────────────────────────────────────
    def _get_or_create_user(self):
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@tradeplatform.com',
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Admin',
                'last_name': 'User',
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(f'   👤 Created superuser: admin / admin123')
        else:
            self.stdout.write(f'   👤 Using existing user: {user.username}')
        return user

    # ─────────────────────────────────────────────
    def _seed_vendors(self):
        """
        Company model fields:
        name, company_type, billing_address, shipping_address,
        payment_terms, tax_id, default_currency, credit_limit,
        internal_notes, is_active
        Contact model fields: company, first_name, last_name, email, phone, title
        """
        from apps.companies.models import Company, Contact

        vendors_data = [
            {
                'company': {
                    'name': 'Arrow Electronics',
                    'company_type': 'vendor',
                    'default_currency': 'USD',
                    'payment_terms': 'Net 30',
                    'internal_notes': 'Major distributor. Strong on TI and Infineon parts.',
                },
                'contact': {
                    'first_name': 'John',
                    'last_name': 'Smith',
                    'email': 'rfq@arrow.com',
                    'phone': '+1-800-777-2776',
                    'title': 'Sales Manager',
                }
            },
            {
                'company': {
                    'name': 'Mouser Electronics',
                    'company_type': 'vendor',
                    'default_currency': 'USD',
                    'payment_terms': 'Net 30',
                    'internal_notes': 'Good for small-to-mid quantities. Fast quotes.',
                },
                'contact': {
                    'first_name': 'Sarah',
                    'last_name': 'Johnson',
                    'email': 'quotes@mouser.com',
                    'phone': '+1-800-346-6873',
                    'title': 'Account Manager',
                }
            },
            {
                'company': {
                    'name': 'Digi-Key Corporation',
                    'company_type': 'vendor',
                    'default_currency': 'USD',
                    'payment_terms': 'Net 30',
                    'internal_notes': 'Best pricing on larger volumes. Strong CoC documentation.',
                },
                'contact': {
                    'first_name': 'Mike',
                    'last_name': 'Chen',
                    'email': 'rfq@digikey.com',
                    'phone': '+1-800-344-4539',
                    'title': 'Sales Representative',
                }
            },
            {
                'company': {
                    'name': 'Avnet Components',
                    'company_type': 'vendor',
                    'default_currency': 'USD',
                    'payment_terms': 'Net 45',
                    'internal_notes': 'Good for AS9120 certified parts.',
                },
                'contact': {
                    'first_name': 'Lisa',
                    'last_name': 'Park',
                    'email': 'quotes@avnet.com',
                    'phone': '+1-480-643-2000',
                    'title': 'Sales Engineer',
                }
            },
        ]

        vendors = []
        for v in vendors_data:
            company, created = Company.objects.get_or_create(
                name=v['company']['name'],
                defaults={**v['company'], 'is_active': True}
            )
            # Create primary contact if needed
            if not company.contacts.filter(is_primary=True).exists():
                Contact.objects.create(
                    company=company,
                    is_primary=True,
                    **v['contact']
                )
            vendors.append(company)
            self.stdout.write(
                f'   🏢 {"Created" if created else "Found  "} vendor: {company.name}'
                f' ({v["contact"]["email"]})'
            )
        return vendors

    # ─────────────────────────────────────────────
    def _seed_customer(self):
        from apps.companies.models import Company, Contact

        customer, created = Company.objects.get_or_create(
            name='Apex Semiconductors Pvt Ltd',
            defaults={
                'company_type': 'customer',
                'default_currency': 'USD',
                'payment_terms': 'Net 30',
                'billing_address': '42 Electronics Park, Whitefield, Bangalore 560066, India',
                'is_active': True,
            }
        )
        if created or not customer.contacts.filter(is_primary=True).exists():
            Contact.objects.get_or_create(
                company=customer,
                email='procurement@apexsemi.com',
                defaults={
                    'first_name': 'Ravi',
                    'last_name': 'Mehta',
                    'phone': '+91-80-4567-8900',
                    'title': 'Senior Procurement Manager',
                    'is_primary': True,
                }
            )
        self.stdout.write(
            f'   👥 {"Created" if created else "Found  "} customer: {customer.name}'
        )
        return customer

    # ─────────────────────────────────────────────
    def _seed_parts(self, user):
        """
        Part model fields:
        part_number, manufacturer, manufacturer_code, description,
        uom, condition, is_hazardous, alternate_pn, superseded_pn,
        internal_notes, tags, status, created_by
        """
        from apps.parts.models import Part

        parts_data = [
            {
                'part_number': 'LM317T',
                'manufacturer': 'Texas Instruments',
                'description': 'Adjustable Voltage Regulator, 1.5A, TO-220',
                'uom': 'PCS',
                'condition': 'new',
                'tags': 'voltage-regulator,linear,TO-220',
                'status': 'active',
            },
            {
                'part_number': 'TIP122',
                'manufacturer': 'STMicroelectronics',
                'description': 'NPN Darlington Transistor, 100V 5A TO-220',
                'uom': 'PCS',
                'condition': 'new',
                'tags': 'transistor,darlington,NPN,TO-220',
                'status': 'active',
            },
            {
                'part_number': 'IRF540N',
                'manufacturer': 'Infineon Technologies',
                'description': 'N-Channel Power MOSFET, 100V 33A TO-220',
                'uom': 'PCS',
                'condition': 'new',
                'tags': 'mosfet,n-channel,power,TO-220',
                'status': 'active',
            },
        ]

        parts = []
        for p in parts_data:
            obj, created = Part.objects.get_or_create(
                part_number=p['part_number'],
                defaults={**p, 'created_by': user}
            )
            parts.append(obj)
            self.stdout.write(
                f'   🔩 {"Created" if created else "Found  "} part: {obj.part_number}'
                f' — {obj.description}'
            )
        return parts

    # ─────────────────────────────────────────────
    def _seed_email_account(self):
        from apps.email_integration.models import EmailAccount

        account, created = EmailAccount.objects.get_or_create(
            email='rfq@yourcompany.com',
            defaults={
                'name': 'Main RFQ Inbox (Seed)',
                'imap_host': 'imap.gmail.com',
                'imap_port': 993,
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'use_tls': True,
                'use_oauth2': False,
                'is_active': True,
            }
        )
        self.stdout.write(
            f'   📧 {"Created" if created else "Found  "} email account: {account.email}'
        )
        return account

    # ─────────────────────────────────────────────
    def _seed_customer_inquiry_email(self, account):
        from apps.email_integration.models import EmailLog, ParsedEmailData

        email_body = """Hi,

We are looking to source the following electronic components urgently
for our Q2 production run. Please provide your best price and
availability ASAP.

Component Requirements:

1. LM317T     Qty: 150 pcs    Condition: New
2. TIP122     Qty: 75 pcs     Condition: New or Refurbished acceptable
3. IRF540N    Qty: 200 pcs    Condition: New only

All parts must have valid certification (CoC preferred).
Delivery required within 3 weeks to our Bangalore facility.

Please quote in USD.

Customer Name: Apex Semiconductors Pvt Ltd
Currency: USD

Regards,
Ravi Mehta
Senior Procurement Manager
Apex Semiconductors Pvt Ltd
procurement@apexsemi.com
+91-80-4567-8900"""

        log, created = EmailLog.objects.get_or_create(
            gmail_message_id='seed_inquiry_001',
            defaults={
                'account': account,
                'direction': 'inbound',
                'from_address': 'Ravi Mehta <procurement@apexsemi.com>',
                'to_addresses': 'rfq@yourcompany.com',
                'subject': 'Urgent RFQ – LM317T, TIP122, IRF540N components',
                'body_text': email_body,
                'status': 'parsed',
                'received_at': timezone.now() - timedelta(hours=2),
                'relevance_score': 0.95,
                'relevance_reason': 'Matched: rfq, qty, component, part number',
            }
        )
        self.stdout.write(
            f'   📨 {"Created" if created else "Found  "} customer inquiry email'
            f' (id={log.pk})'
        )

        parsed_lines = [
            {'pn': 'LM317T',  'qty': 150, 'description': 'Adjustable Voltage Regulator', 'cd': 'New'},
            {'pn': 'TIP122',  'qty': 75,  'description': 'NPN Darlington Transistor',    'cd': 'New'},
            {'pn': 'IRF540N', 'qty': 200, 'description': 'N-Channel MOSFET',             'cd': 'New'},
        ]
        parsed, _ = ParsedEmailData.objects.get_or_create(
            email_log=log,
            defaults={
                'raw_parsed': {
                    'lines': parsed_lines,
                    'customer_name': 'Apex Semiconductors Pvt Ltd',
                    'currency': 'USD',
                },
                'confirmed_lines': parsed_lines,
                'is_confirmed': False,
            }
        )
        return log, parsed

    # ─────────────────────────────────────────────
    def _seed_inquiry(self, customer, user):
        from apps.rfq.models import RFQ, RFQLine
        from apps.parts.models import Part

        rfq, created = RFQ.objects.get_or_create(
            source='email',
            customer=customer,
            external_notes='From email: Urgent RFQ – LM317T, TIP122, IRF540N components',
            defaults={
                'payment_terms': 'Net 30',
                'internal_notes': 'Urgent Q2 production run. Customer requires CoC on all parts.',
                'created_by': user,
                'status': 'open',
            }
        )

        if created:
            lines_data = [
                ('LM317T',  'Adjustable Voltage Regulator, 1.5A, TO-220', 150, 'New'),
                ('TIP122',  'NPN Darlington Transistor, 100V 5A',          75,  'New'),
                ('IRF540N', 'N-Channel Power MOSFET, 100V 33A',            200, 'New'),
            ]
            for i, (pn, desc, qty, cd) in enumerate(lines_data, start=1):
                part = Part.objects.filter(part_number=pn).first()
                RFQLine.objects.create(
                    rfq=rfq,
                    line_number=i,
                    part=part,
                    part_number_raw=pn,
                    description=desc,
                    quantity=qty,
                    condition_required=cd,
                )

        self.stdout.write(
            f'   📋 {"Created" if created else "Found  "} inquiry: {rfq.rfq_number}'
            f' with {rfq.lines.count()} lines'
        )
        return rfq

    # ─────────────────────────────────────────────
    def _seed_vendor_rfqs(self, inquiry, vendors, user):
        from apps.vendor_rfq.models import VendorRFQ, VendorRFQLine, VendorQuoteLine

        lines = list(inquiry.lines.order_by('line_number'))
        vrfqs = []

        arrow   = next(v for v in vendors if 'Arrow'   in v.name)
        mouser  = next(v for v in vendors if 'Mouser'  in v.name)
        digikey = next(v for v in vendors if 'Digi'    in v.name)
        avnet   = next(v for v in vendors if 'Avnet'   in v.name)

        # ── Arrow: all 3 parts, SENT (reply email pending verification) ──
        vrfq_arrow, created = VendorRFQ.objects.get_or_create(
            inquiry=inquiry, vendor=arrow,
            defaults={
                'status': VendorRFQ.STATUS_SENT,
                'sent_at': timezone.now() - timedelta(hours=1, minutes=30),
                'created_by': user,
                'notes': 'Arrow has strong stock on TI and Infineon. Requested CoC on all lines.',
            }
        )
        if created:
            for i, line in enumerate(lines, start=1):
                VendorRFQLine.objects.create(
                    vendor_rfq=vrfq_arrow,
                    inquiry_line=line,
                    part_number=line.part_number_raw,
                    quantity=line.quantity,
                    condition=line.condition_required,
                    line_number=i,
                )
        vrfqs.append(vrfq_arrow)
        self.stdout.write(
            f'   📤 {"Created" if created else "Found  "} VRFQ → {arrow.name}'
            f' [{vrfq_arrow.rfq_number}] status=SENT'
        )

        # ── Mouser: all 3 parts, QUOTED ──
        vrfq_mouser, created = VendorRFQ.objects.get_or_create(
            inquiry=inquiry, vendor=mouser,
            defaults={
                'status': VendorRFQ.STATUS_QUOTED,
                'sent_at': timezone.now() - timedelta(hours=3),
                'created_by': user,
            }
        )
        if created:
            mouser_quotes = [
                # (pn,        qty, price, avail, lead, cond,  cert)
                ('LM317T',  150, 0.85,  500,  7,  'New', 'CoC'),
                ('TIP122',  75,  1.20,  300,  10, 'New', 'CoC'),
                ('IRF540N', 200, 2.45,  800,  5,  'New', 'AS9120'),
            ]
            for i, (pn, qty, price, avail, lead, cond, cert) in enumerate(mouser_quotes, start=1):
                vline = VendorRFQLine.objects.create(
                    vendor_rfq=vrfq_mouser,
                    inquiry_line=lines[i - 1],
                    part_number=pn,
                    quantity=qty,
                    condition=cond,
                    line_number=i,
                )
                VendorQuoteLine.objects.create(
                    vendor_rfq_line=vline,
                    unit_price=price,
                    quantity_available=avail,
                    lead_time_days=lead,
                    condition=cond,
                    certification=cert,
                    source=VendorQuoteLine.SOURCE_MANUAL,
                    entered_by=user,
                )
        vrfqs.append(vrfq_mouser)
        self.stdout.write(
            f'   📤 {"Created" if created else "Found  "} VRFQ → {mouser.name}'
            f' [{vrfq_mouser.rfq_number}] status=QUOTED (3/3 lines)'
        )

        # ── Digi-Key: 2 parts only (LM317T + IRF540N), QUOTED with better prices ──
        vrfq_digikey, created = VendorRFQ.objects.get_or_create(
            inquiry=inquiry, vendor=digikey,
            defaults={
                'status': VendorRFQ.STATUS_QUOTED,
                'sent_at': timezone.now() - timedelta(hours=2),
                'created_by': user,
                'notes': 'No stock on TIP122. Quoted LM317T and IRF540N only.',
            }
        )
        if created:
            # Only lines 0 (LM317T) and 2 (IRF540N)
            digikey_quotes = [
                (lines[0], 'LM317T',  150, 0.79, 1000, 3, 'New', 'CoC'),
                (lines[2], 'IRF540N', 200, 2.30, 400,  8, 'New', 'CoC'),
            ]
            for i, (line, pn, qty, price, avail, lead, cond, cert) in enumerate(digikey_quotes, start=1):
                vline = VendorRFQLine.objects.create(
                    vendor_rfq=vrfq_digikey,
                    inquiry_line=line,
                    part_number=pn,
                    quantity=qty,
                    condition=cond,
                    line_number=i,
                )
                VendorQuoteLine.objects.create(
                    vendor_rfq_line=vline,
                    unit_price=price,
                    quantity_available=avail,
                    lead_time_days=lead,
                    condition=cond,
                    certification=cert,
                    source=VendorQuoteLine.SOURCE_MANUAL,
                    entered_by=user,
                )
        vrfqs.append(vrfq_digikey)
        self.stdout.write(
            f'   📤 {"Created" if created else "Found  "} VRFQ → {digikey.name}'
            f' [{vrfq_digikey.rfq_number}] status=QUOTED (2/3 lines)'
        )

        # ── Avnet: all 3 parts, still DRAFT ──
        vrfq_avnet, created = VendorRFQ.objects.get_or_create(
            inquiry=inquiry, vendor=avnet,
            defaults={
                'status': VendorRFQ.STATUS_DRAFT,
                'created_by': user,
                'notes': 'Potential for AS9120 certified stock.',
            }
        )
        if created:
            for i, line in enumerate(lines, start=1):
                VendorRFQLine.objects.create(
                    vendor_rfq=vrfq_avnet,
                    inquiry_line=line,
                    part_number=line.part_number_raw,
                    quantity=line.quantity,
                    condition=line.condition_required,
                    line_number=i,
                )
        vrfqs.append(vrfq_avnet)
        self.stdout.write(
            f'   📤 {"Created" if created else "Found  "} VRFQ → {avnet.name}'
            f' [{vrfq_avnet.rfq_number}] status=DRAFT'
        )

        return vrfqs

    # ─────────────────────────────────────────────
    def _seed_vendor_quote_email(self, account, vrfqs, user):
        """
        Seed Arrow's reply email — already AI-parsed,
        sitting in 'Vendor Quote Replies' queue awaiting user verification.
        """
        from apps.email_integration.models import EmailLog
        from apps.vendor_rfq.models import ParsedVendorQuote, VendorRFQ

        arrow_vrfq = next((v for v in vrfqs if 'Arrow' in v.vendor.name), None)
        if not arrow_vrfq:
            self.stdout.write('   ⚠️  Arrow VRFQ not found, skipping reply email.')
            return None

        reply_body = f"""Hi,

Thank you for your inquiry reference {arrow_vrfq.rfq_number}.

We are pleased to provide the following quotation:

Part #      | Unit Price | Qty Avail | Lead Time | Condition | Certification
LM317T      | $0.92      | 2,000 pcs | 5 days    | New       | CoC
TIP122      | $1.35      | 500 pcs   | 7 days    | New       | CoC
IRF540N     | $2.60      | 1,500 pcs | 4 days    | New       | AS9120 + CoC

Notes:
- All parts are original factory stock with full manufacturer traceability
- CoC and test reports available on request
- Prices valid for 30 days from today
- DDP Bangalore included for orders exceeding $500

Please confirm your order at your earliest convenience and we will
reserve stock for you.

Best regards,
John Smith
Sales Manager – Arrow Electronics
rfq@arrow.com | +1-800-777-2776"""

        log, created = EmailLog.objects.get_or_create(
            gmail_message_id='seed_arrow_reply_001',
            defaults={
                'account': account,
                'direction': 'inbound',
                'from_address': 'John Smith <rfq@arrow.com>',
                'to_addresses': 'rfq@yourcompany.com',
                'subject': f'RE: RFQ {arrow_vrfq.rfq_number} – Component Inquiry',
                'body_text': reply_body,
                'status': 'parsed',
                'received_at': timezone.now() - timedelta(minutes=25),
            }
        )
        self.stdout.write(
            f'   📩 {"Created" if created else "Found  "} Arrow reply email (id={log.pk})'
        )

        pq, created = ParsedVendorQuote.objects.get_or_create(
            email_log=log,
            defaults={
                'vendor_rfq': arrow_vrfq,
                'raw_parsed': {
                    'lines': [
                        {
                            'pn': 'LM317T',
                            'unit_price': 0.92,
                            'qty_available': 2000,
                            'lead_time_days': 5,
                            'condition': 'New',
                            'certification': 'CoC',
                            'notes': '',
                        },
                        {
                            'pn': 'TIP122',
                            'unit_price': 1.35,
                            'qty_available': 500,
                            'lead_time_days': 7,
                            'condition': 'New',
                            'certification': 'CoC',
                            'notes': '',
                        },
                        {
                            'pn': 'IRF540N',
                            'unit_price': 2.60,
                            'qty_available': 1500,
                            'lead_time_days': 4,
                            'condition': 'New',
                            'certification': 'AS9120 + CoC',
                            'notes': 'Original factory stock',
                        },
                    ],
                    'vendor_notes': 'Prices valid 30 days. DDP Bangalore for orders over $500.',
                },
                'is_confirmed': False,
            }
        )

        # Link the reply email to the VendorRFQ
        arrow_vrfq.reply_email = log
        arrow_vrfq.save(update_fields=['reply_email'])

        self.stdout.write(
            f'   🤖 {"Created" if created else "Found  "} ParsedVendorQuote'
            f' (pending verification, id={pq.pk})'
        )
        return pq