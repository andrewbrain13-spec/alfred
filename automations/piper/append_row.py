#!/usr/bin/env python3
"""Automation #2: log a Piper NLC/RLC checklist into the OneDrive tracker.

When Piper emails an NLC (New Lease Checklist) or RLC (Renewal Lease Checklist)
share link to the distribution list, append a row to Table1 in
`NLC tracking.xlsx` on OneDrive, putting the share link in the Link column.

Columns (A..J): Tenant | date | N/R/T | Kimmy | John | Ashley | Tracy | Dawn |
Darrell | Link. We fill Tenant, date, type (N/R), and Link; the per-person
columns are left blank for you to mark.

Env:
  ALFRED_MESSAGE_JSON     path to the Piper email JSON (set by Alfred)
  ALFRED_DRY_RUN          "1" = log only, don't write (default "1")
  ALFRED_TENANT_ID / ALFRED_CLIENT_ID   Graph app registration
  PIPER_TRACKING_PATH     drive-relative path (default "NLC tracking.xlsx")
  PIPER_TABLE             table name (default "Table1")

NOTE: tenant/type/link extraction is best-effort until we tighten it against a
real Piper email. Runs in dry-run by default so you can confirm the parse.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from alfred.graph import GraphClient

# A SharePoint/OneDrive share link, as emailed to a distribution list.
_SHARE_RE = r"https?://[^\s\"'<>]*sharepoint[^\s\"'<>]*"
_LINK_RE = re.compile(_SHARE_RE, re.IGNORECASE)
# Prefer the URL right after the "NLC Link:" / "RLC Link:" label.
_LABELED_LINK_RE = re.compile(
    r"(?:NLC|RLC|New Lease Checklist|Renewal Lease Checklist)\s*Link\s*:.*?(" + _SHARE_RE + ")",
    re.IGNORECASE | re.DOTALL,
)
_TYPES = r"(?:new lease checklist|renewal lease checklist|nlc|rlc)"


def _load_email() -> dict:
    path = os.environ.get("ALFRED_MESSAGE_JSON")
    if path and os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return json.loads(sys.stdin.read() or "{}")


def _extract_link(email: dict) -> str:
    for field in ("body_text", "body_html"):
        text = email.get(field, "") or ""
        m = _LABELED_LINK_RE.search(text)
        if m:
            return m.group(1).rstrip(").,>")
    for field in ("body_text", "body_html"):
        m = _LINK_RE.search(email.get(field, "") or "")
        if m:
            return m.group(0).rstrip(").,>")
    return ""


def _extract_type(email: dict) -> str:
    text = f"{email.get('subject','')} {email.get('body_text','')}".lower()
    if "renewal" in text or "rlc" in text:
        return "R"
    if "new lease" in text or "nlc" in text:
        return "N"
    return ""


def _extract_tenant(email: dict) -> str:
    """Tenant name from the subject, handling both orders seen in samples:

        'NLC - Mission Kitchen & Bath'   (type first)  -> Mission Kitchen & Bath
        'SIRO - RLC'                     (tenant first) -> SIRO
    """
    subj = re.sub(r"^\s*(re|fw|fwd)\s*:\s*", "", email.get("subject", "") or "", flags=re.I).strip()
    m = re.match(rf"^\s*{_TYPES}\s*[-:]\s*(.+)$", subj, re.IGNORECASE)
    if not m:
        m = re.match(rf"^(.+?)\s*[-:]\s*{_TYPES}\s*$", subj, re.IGNORECASE)
    cand = m.group(1) if m else subj
    return re.sub(r"\s*\b20\d{2}\b\s*$", "", cand).strip()


def main() -> int:
    dry_run = os.environ.get("ALFRED_DRY_RUN", "1") == "1"
    item_path = os.environ.get("PIPER_TRACKING_PATH", "NLC tracking.xlsx")
    table = os.environ.get("PIPER_TABLE", "Table1")

    email = _load_email()
    link = _extract_link(email)
    if not link:
        print("SKIPPED: no share link found in the email; refine _LINK_RE.")
        return 0

    tenant = _extract_tenant(email)
    typ = _extract_type(email)
    row = [tenant, date.today(), typ, "", "", "", "", "", "", link]

    if dry_run:
        print(f"DRY-RUN: would append row to {item_path}!{table}: "
              f"Tenant={tenant!r} date={date.today()} type={typ!r} Link={link}")
        return 0

    GraphClient().add_table_row(item_path, table, row)
    print(f"ROW ADDED to {item_path}!{table}: {tenant!r} ({typ}) -> {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
