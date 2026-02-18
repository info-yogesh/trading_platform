# TradePlatform — RFQ & Trading Management System

A full-featured, web-based multi-user trading and RFQ management platform built with Django.

## Features

- **Dashboard** — KPIs, conversion rates, profit summaries, aging alerts
- **RFQ Module** — Manual entry, bulk paste import, AI-assisted email parsing, full audit trail
- **Quotes** — Real-time margin preview, template-based, version tracking, PDF/print output
- **Sales Orders** — Full lifecycle from quote to shipment, payment tracking
- **Purchase Orders** — Additional charge allocation (transport/customs) affecting profitability
- **Receiving (GRN)** — Partial receiving, quality check flags, automatic inventory update
- **Inventory** — Own stock, vendor offers, customer offers, push lists
- **Parts Master** — Centralized PN database, bulk CSV upload, hazardous flags
- **Companies** — Vendors & customers, contacts, credit limits
- **Email Integration** — IMAP/SMTP, OAuth2, AI-assisted email parsing

## Architecture

```
trading_platform/
├── manage.py
├── requirements.txt
├── trading_platform/          # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── dashboard/
│   ├── parts/
│   ├── companies/
│   ├── inventory/
│   ├── rfq/
│   ├── quotes/
│   ├── sales_orders/
│   ├── purchase_orders/
│   ├── receiving/
│   └── email_integration/
├── templates/
│   ├── base/
│   │   ├── base.html
│   │   └── login.html
│   ├── dashboard/
│   ├── parts/
│   ├── companies/
│   ├── inventory/
│   ├── rfq/
│   ├── quotes/
│   ├── sales_orders/
│   ├── purchase_orders/
│   ├── receiving/
│   └── email_integration/
└── static/

```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Install dependencies

```bash
cd trading_platform
pip install -r requirements.txt
```

### 3. Configure settings

Edit `trading_platform/settings.py`:
- Change `SECRET_KEY` to a secure random value
- Set `DEBUG = False` for production
- Configure `DATABASES` (default is SQLite, switch to PostgreSQL for production)
- Set `ALLOWED_HOSTS`

### 4. Run migrations

```bash
python manage.py makemigrations parts companies inventory rfq quotes sales_orders purchase_orders receiving email_integration
python manage.py migrate
```

### 5. Create a superuser

```bash
python manage.py createsuperuser
```

### 6. Collect static files (production)

```bash
python manage.py collectstatic
```

### 7. Run the development server

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

---

## Workflow Overview

```
Email / Manual Input
        ↓
      RFQ
        ↓
      Quote  (margin preview per line)
        ↓
   Sales Order
        ↓
  Purchase Order  (+ additional charges → auto profit impact)
        ↓
     Receiving (GRN)
        ↓
   Inventory Updated
        ↓
     Shipment
```

## Profit Calculation

> **Profit = Sell Price − (Cost + Allocated Charges)**

- Line-level margins shown in real time while quoting
- PO additional charges (transport, customs, handling) allocated at line or order level
- All affect deal-level and system-wide profitability reporting

## Roles (configure via Django admin)

| Role | Access |
|------|--------|
| Administrator | Full access |
| Sales User | RFQ, Quotes, SO |
| Purchasing User | PO, Receiving |
| Operations User | Inventory, Receiving |
| Viewer | Read-only |

## Production Deployment

For production:
1. Switch `DATABASES` to PostgreSQL
2. Set `DEBUG = False`
3. Configure SMTP for outgoing email
4. Use `gunicorn` + `nginx`
5. Set up SSL certificate

```bash
pip install gunicorn psycopg2-binary
gunicorn trading_platform.wsgi:application --bind 0.0.0.0:8000
```

## Self-Hosted & Privacy

- **No third-party data exposure** — runs entirely on your infrastructure
- **Full database ownership** — SQLite or PostgreSQL, you control the data
- **Role-based visibility** — control who sees costs, margins, vendor data
- **Encrypted storage** — configure at the OS/DB level for full encryption
