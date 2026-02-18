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