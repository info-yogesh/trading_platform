# email_integration/parser.py
import re
import json
import requests
from django.conf import settings

from trading_platform.settings import OPENROUTER_API_KEY


PARSE_SYSTEM_PROMPT = """You extract RFQ line items from emails.
Return ONLY valid JSON in this exact shape:
{
  "lines": [
    {"pn": "PART123", "qty": 100, "description": "N-Channel MOSFET", "cd": "New"}
  ],
  "customer_name": "Acme Corp",
  "currency": "USD"
}
- pn and qty are required for each line. qty must be an integer.
- cd is the condition: New, Used, Refurbished, or NS (new surplus).
- If no line items exist, return {"lines": [], "customer_name": "", "currency": "USD"}
- Output ONLY the JSON object. No explanation, no markdown."""



def parse_email_with_ai(subject, body_text):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openrouter/free",
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Subject: {subject}\n\nBody:\n{body_text[:4000]}"},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(match.group()) if match else {"lines": []}


VENDOR_QUOTE_SYSTEM_PROMPT = """You extract vendor quote data from emails. Be flexible — vendors write prices in many formats.

Price formats you must handle:
- "Price:1000 $"  → unit_price: 1000
- "$ 1293.26"     → unit_price: 1293.26
- "USD 2.50"      → unit_price: 2.50
- "$0.92/pc"      → unit_price: 0.92
- "1.25 per unit" → unit_price: 1.25

Lead time formats:
- "2 days", "within 2 days", "2 business days" → lead_time_days: 2
- "2 weeks" → lead_time_days: 14
- "immediate" → lead_time_days: 1

Return ONLY valid JSON in this exact shape:
{
  "lines": [
    {
      "pn": "IRF540N",
      "unit_price": 1000.0,
      "qty_available": 0,
      "lead_time_days": 2,
      "condition": "AD",
      "certification": "A+",
      "notes": ""
    }
  ],
  "vendor_notes": "Any overall notes from the vendor"
}

Rules:
- pn and unit_price are REQUIRED. Skip lines where price is completely absent.
- qty_available: use 0 if not mentioned.
- lead_time_days: integer only. Convert text to days. null if not mentioned.
- condition: extract exactly as written (New, Used, AD, NS, Refurbished, etc.)
- certification: extract exactly as written (CoC, A+, AAR, AS9120, etc.)
- If vendor says they cannot supply a part, omit it entirely.
- Output ONLY the JSON object. No explanation, no markdown, no code fences."""


def parse_vendor_quote_email(subject, body_text, rfq_lines=None):
    """
    Parse a vendor's quote reply email.
    rfq_lines: list of part numbers we sent — helps AI match lines.
    """
    context = ""
    if rfq_lines:
        context = "Parts we originally requested:\n" + "\n".join(
            f"  - {pn}" for pn in rfq_lines
        ) + "\n\n"

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openrouter/free",
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": VENDOR_QUOTE_SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}Subject: {subject}\n\nEmail:\n{body_text[:4000]}"},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(match.group()) if match else {"lines": []}