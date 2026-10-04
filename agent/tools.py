"""
Tools the agent is allowed to use.

Everything here is intentionally scoped to a small, local, fake "company
environment" instead of a real website or a real accounting tool:
  - mock_company_app/invoices/      -> stands in for "a shared drive full of invoices"
  - mock_company_app/internal_system.json -> stands in for "our internal system"

This keeps the prototype safe to run and share (no real credentials, no
real third-party systems -- per the submission rules) while still giving
the agent real files to read, real parsing to get wrong, and a real
read/write/verify loop to perform.
"""

import json
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVOICE_DIR = os.path.join(BASE_DIR, "mock_company_app", "invoices")
SYSTEM_FILE = os.path.join(BASE_DIR, "mock_company_app", "internal_system.json")


def list_invoices():
    """Return metadata for every invoice file: filename, company, date issued."""
    results = []
    for fname in sorted(os.listdir(INVOICE_DIR)):
        path = os.path.join(INVOICE_DIR, fname)
        if not fname.endswith(".txt"):
            continue
        text = open(path).read()
        company = _grab(text, "Company")
        date_issued = _grab(text, "Date Issued")
        results.append({
            "filename": fname,
            "path": path,
            "company": company,
            "date_issued": date_issued,
        })
    return results


def read_invoice(path):
    with open(path) as f:
        return f.read()


def extract_fields(invoice_text):
    """
    Pull the fields we actually care about out of an invoice.

    Returns a dict:
      { "ok": bool, "fields": {...}, "missing": [...] }

    "ok" is False if a required field is missing or unparseable. This is
    the main place a real invoice (messy, inconsistent, occasionally
    incomplete) causes the agent to fail -- which is the point: the task
    brief explicitly wants to see failure detection and recovery, not just
    a happy path.
    """
    fields = {
        "invoice_number": _grab(invoice_text, "Invoice Number"),
        "company": _grab(invoice_text, "Company"),
        "amount": _grab(invoice_text, "Amount"),
        "due_date": _grab(invoice_text, "Due Date"),
    }

    missing = []
    if not fields["amount"]:
        missing.append("amount")
    if not fields["due_date"] or not _looks_like_date(fields["due_date"]):
        missing.append("due_date")

    return {"ok": len(missing) == 0, "fields": fields, "missing": missing}


def write_to_system(entry):
    """
    Append a verified entry to the internal system file.

    Returns {"ok": bool, "reason": str}. Writing can fail validation
    (e.g. if a required field is still missing) -- the agent is expected
    to check this return value rather than assume the write succeeded.
    """
    if not entry.get("amount") or not entry.get("due_date"):
        return {"ok": False, "reason": "entry is missing amount or due_date, refusing to write"}

    with open(SYSTEM_FILE) as f:
        db = json.load(f)

    # idempotency: don't double-enter the same invoice number
    for existing in db["entries"]:
        if existing["invoice_number"] == entry["invoice_number"]:
            return {"ok": False, "reason": f"invoice {entry['invoice_number']} already exists in the system"}

    entry["entered_at"] = datetime.now().isoformat(timespec="seconds")
    db["entries"].append(entry)

    with open(SYSTEM_FILE, "w") as f:
        json.dump(db, f, indent=2)

    return {"ok": True, "reason": "written"}


def verify_entry(invoice_number):
    """Read the system back and confirm the entry is actually there with the right data."""
    with open(SYSTEM_FILE) as f:
        db = json.load(f)
    for entry in db["entries"]:
        if entry["invoice_number"] == invoice_number:
            return {"ok": True, "entry": entry}
    return {"ok": False, "entry": None}


# --- small helpers -----------------------------------------------------

def _grab(text, label):
    """Pull 'Label: value' out of the invoice text. Returns '' if blank/missing."""
    # Note: using [ \t]* here (not \s*) is deliberate -- \s* also matches
    # newlines, which let this silently grab text from the *next* line
    # when a field was left blank (e.g. "Amount:\n----"). Caught by testing
    # against invoice_102.txt, where a blank Amount field was being read as
    # the divider line below it instead of being flagged as missing.
    match = re.search(rf"^{re.escape(label)}:[ \t]*(.*)$", text, re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def _looks_like_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False
