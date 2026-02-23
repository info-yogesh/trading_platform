import re
import json
import requests
from django.conf import settings

from trading_platform.settings import OPENROUTER_API_KEY, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, USE_PAID_MODEL


use_paid_model = USE_PAID_MODEL

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
    """
    Parse new inquiry email.
    If use_paid_model=True → Azure
    Else → OpenRouter
    """

    if use_paid_model:
        print("AI EMAIL parsing with paid model")
        # ---- Azure ----
        url = (
            f"{AZURE_OPENAI_ENDPOINT}"
            f"openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
            f"?api-version={AZURE_OPENAI_API_VERSION}"
        )

        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        }

        payload = {
            "messages": [
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Subject: {subject}\n\nBody:\n{body_text[:4000]}",
                },
            ],
            "max_tokens": 1500,
            "temperature": 0,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

    else:
        print("AI EMAIL parsing without paid model")
        # ---- OpenRouter ----
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "max_tokens": 1500,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Subject: {subject}\n\nBody:\n{body_text[:4000]}",
                    },
                ],
            },
            timeout=30,
        )

    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group()) if match else {"lines": []}


VENDOR_QUOTE_SYSTEM_PROMPT = """
You extract vendor quote data from email replies.

IMPORTANT:
- Extract data ONLY from the vendor's reply section.
- Ignore quoted previous emails (e.g., lines starting with "On Mon,", ">", or prior inquiry text).
- Ignore signatures and disclaimers unless they contain quote information.
- Ignore HTML entities like &amp; (treat them as &).

Price formats to handle:
- "Price:1000 $" → 1000
- "$ 1293.26"
- "USD 2.50"
- "$0.92/pc"
- "1.25 per piece"
- "USD 185.00 per piece"

Lead time normalization:
- "2 days", "2 business days", "within 2 days" → 2
- "3 business days" → 3
- "2 weeks" → 14
- "5 weeks" → 35
- "immediate" → 1

Quantity formats:
- "Available Quantity: 120 pcs"
- "120 pcs available"
- If not mentioned → 0

Condition rules:
- Extract main condition keyword only:
  New, Used, Refurbished, NS, AD
- If text is "Used (Tested & Fully Functional)" → condition = "Used"

Certification rules:
- Extract short certification keyword if present:
  CoC, A+, AAR, AS9120
- If text says "Certificate of Conformance (CoC)" → certification = "CoC"
- If only descriptive text exists → return short meaningful keyword
- If none → empty string

Skip any part where price is missing.
If vendor says they cannot supply → omit that line entirely.

Return ONLY valid JSON in this exact shape:

{
  "lines": [
    {
      "pn": "IRF540N",
      "unit_price": 1000.0,
      "qty_available": 0,
      "lead_time_days": 2,
      "condition": "New",
      "certification": "CoC",
      "notes": ""
    }
  ],
  "vendor_notes": "Any overall notes from vendor"
}

No explanation.
No markdown.
Only JSON.
"""


def parse_vendor_quote_email(subject, body_text, rfq_lines=None):
    """
    Parse vendor quote email.
    If use_paid_model=True → Azure
    Else → OpenRouter
    """

    context = ""
    if rfq_lines:
        context = "Parts we originally requested:\n" + "\n".join(
            f"  - {pn}" for pn in rfq_lines
        ) + "\n\n"

    user_content = f"{context}Subject: {subject}\n\nEmail:\n{body_text[:4000]}"

    if use_paid_model:
        # ---- Azure ----
        url = (
            f"{AZURE_OPENAI_ENDPOINT}"
            f"openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
            f"?api-version={AZURE_OPENAI_API_VERSION}"
        )

        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        }

        payload = {
            "messages": [
                {"role": "system", "content": VENDOR_QUOTE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 1500,
            "temperature": 0,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

    else:
        # ---- OpenRouter ----
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "max_tokens": 1500,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": VENDOR_QUOTE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            },
            timeout=30,
        )

    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    try:
        result = json.loads(raw)
        print(result)
        return result
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group()) if match else {"lines": []}


EMAIL_CLASSIFIER_SYSTEM_PROMPT = """You classify trading emails.

Classify the email into ONE of the following types:

- "new_inquiry" → A customer sending a new RFQ / asking for parts / requesting quotation.
- "vendor_response" → A vendor replying to an RFQ with pricing, availability, lead time, or quotation details.

Rules:
- If the email contains prices, unit cost, availability, lead time, certifications, or quote references → vendor_response.
- If the email is requesting quote, sending part numbers with qty, or asking for availability → new_inquiry.
- Ignore signatures and disclaimers.
- Be decisive. Choose only one.

Return ONLY valid JSON in this exact format:
{
  "email_type": "new_inquiry"
}

No explanation. No markdown. Only JSON.
"""

def classify_email(subject, body_text):
    """
    Classify email as:
    - new_inquiry
    - vendor_response

    If use_paid_model=True → Uses Azure OpenAI
    If False → Uses OpenRouter
    """

    if use_paid_model:
        # ---- Azure OpenAI ----
        url = (
            f"{AZURE_OPENAI_ENDPOINT}"
            f"openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
            f"?api-version={AZURE_OPENAI_API_VERSION}"
        )

        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        }

        payload = {
            "messages": [
                {"role": "system", "content": EMAIL_CLASSIFIER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Subject: {subject}\n\nEmail:\n{body_text[:4000]}",
                },
            ],
            "max_tokens": 200,
            "temperature": 0,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

    else:
        # ---- OpenRouter (Free Model) ----
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "max_tokens": 200,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": EMAIL_CLASSIFIER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Subject: {subject}\n\nEmail:\n{body_text[:4000]}",
                    },
                ],
            },
            timeout=30,
        )

        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

    # ---- Common JSON Parsing Logic ----
    try:
        result = json.loads(raw)
        if result.get("email_type") in ["new_inquiry", "vendor_response"]:
            return result["email_type"]
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return result.get("email_type", "new_inquiry")
            except Exception:
                pass

    # Safe fallback (never miss RFQ)
    return "new_inquiry"