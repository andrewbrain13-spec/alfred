#!/usr/bin/env python3
"""Approve a Prism (PrismHR) time-off request via the PrismHR Services API.

TEMPLATE — fill in the endpoint paths for YOUR PrismHR instance.

The PrismHR Services API is REST/JSON and is authenticated with a *web service
user* that your PrismHR administrator (often your PEO) must create. Exact
endpoint paths live behind the authenticated docs at https://api-docs.prismhr.com
and can differ by tenant/version, so they are left as constants to fill in.

This script is called by Alfred's ``run_command`` workflow. It receives the
triggering email as JSON via the ``ALFRED_MESSAGE_JSON`` env var, plus:
  PRISM_API_BASE      e.g. https://<tenant>.prismhr.com/api
  PRISM_API_TOKEN     bearer token / web-service-user token
  ALFRED_DRY_RUN      "1" to parse-and-report only, "0" to actually approve

Usage (Alfred rule):
  - type: run_command
    command: ["python", "automations/prism/prism_approve_api.py"]
"""

from __future__ import annotations

import json
import os
import re
import sys

import requests

# --- FILL THESE IN from your instance's API docs ---------------------------
PENDING_PATH = "/timeOffRequests?status=pending"   # GET: list pending requests
APPROVE_PATH = "/timeOffRequests/{request_id}/approve"  # POST/PUT: approve one
# Field names in the API's JSON for matching (adjust to real schema):
FIELD_ID = "id"
FIELD_EMPLOYEE = "employeeName"
FIELD_START = "startDate"
FIELD_END = "endDate"
# ---------------------------------------------------------------------------


def _session() -> requests.Session:
    token = os.environ["PRISM_API_TOKEN"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    return s


def _load_email() -> dict:
    path = os.environ.get("ALFRED_MESSAGE_JSON")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    # Fallback: read raw email JSON from stdin.
    data = sys.stdin.read()
    return json.loads(data) if data.strip() else {}


def _extract_hint(email: dict) -> str:
    """Pull an employee name / identifier out of the notification text.

    Prism notification wording varies; refine this regex for your emails.
    """
    text = f"{email.get('subject','')}\n{email.get('body_text','')}"
    m = re.search(r"(?:request(?:ed)? by|from)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)", text)
    return m.group(1) if m else ""


def main() -> int:
    base = os.environ["PRISM_API_BASE"].rstrip("/")
    dry_run = os.environ.get("ALFRED_DRY_RUN", "1") == "1"
    email = _load_email()
    hint = _extract_hint(email)

    s = _session()
    resp = s.get(base + PENDING_PATH, timeout=30)
    resp.raise_for_status()
    pending = resp.json()
    if isinstance(pending, dict):  # some APIs wrap in {"data": [...]}
        pending = pending.get("data", pending.get("items", []))

    # Match the request to the notification. Prefer a strong match (name).
    candidates = [
        r for r in pending
        if hint and hint.lower() in str(r.get(FIELD_EMPLOYEE, "")).lower()
    ]
    if not hint:
        print("SKIPPED: could not extract an employee from the email; refine _extract_hint().")
        return 0
    if len(candidates) != 1:
        print(f"SKIPPED: matched {len(candidates)} requests for {hint!r}; refusing to guess.")
        return 0

    req = candidates[0]
    rid = req[FIELD_ID]
    summary = f"{req.get(FIELD_EMPLOYEE)} {req.get(FIELD_START)}..{req.get(FIELD_END)} (id={rid})"

    if dry_run:
        print(f"DRY-RUN: would approve {summary}")
        return 0

    ap = s.post(base + APPROVE_PATH.format(request_id=rid), timeout=30)
    ap.raise_for_status()
    print(f"APPROVED: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
