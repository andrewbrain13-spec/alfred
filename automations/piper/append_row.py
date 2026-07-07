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

import html
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from alfred.graph import GraphClient


def _html_to_text(h: str) -> str:
    """Crudely convert an HTML body to plain text for matching."""
    if not h:
        return ""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return html.unescape(h)


def _email_text(email: dict) -> str:
    """All searchable text of the email: subject + plain body + HTML body.

    Real Outlook mail is usually HTML (body_text empty), so the building name
    lives in body_html — include it here.
    """
    return (
        f"{email.get('subject', '')} \n {email.get('body_text', '')} \n "
        f"{_html_to_text(email.get('body_html', ''))}"
    )

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
    text = _email_text(email).lower()
    if "renewal" in text or "rlc" in text:
        return "R"
    if "new lease" in text or "nlc" in text:
        return "N"
    return ""


def _graph_id(email: dict) -> str:
    uid = email.get("uid", "") or ""
    return uid.split(":", 1)[1] if ":" in uid else ""


def _words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("&", " and ")).split()


# Generic words in building-folder names that shouldn't drive a match on their own.
_STOP = {"plaza", "building", "center", "centre", "office", "offices", "suite",
         "suites", "tower", "place", "the", "llc", "properties", "property",
         "group", "park", "square", "commons", "court"}


def _key_tokens(name: str) -> list[str]:
    """Distinctive tokens of a folder name (drop generic/short words)."""
    return [t for t in _words(name) if len(t) >= 4 and t not in _STOP]


def _match_building_folder(email: dict, folders: list[dict], overrides: dict | None = None) -> dict | None:
    """Pick the folder for the BUILDING the email names.

    The building appears in the email text (e.g. 'New Tenant at Foxridge!'). A
    folder matches if its full name is a token-phrase in the email, OR (for
    folders like 'Foxridge Plaza' when the email just says 'Foxridge') if one of
    its distinctive tokens appears. Conservative: returns a folder only when a
    single one matches, else None.
    """
    overrides = overrides or {}
    tenant = _extract_tenant(email)
    for k, v in overrides.items():  # tenant -> building folder override
        if k.strip().lower() == tenant.strip().lower():
            for f in folders:
                if (f.get("displayName") or "").strip().lower() == v.strip().lower():
                    return f

    words = _words(_email_text(email))
    text_words = set(words)
    joined = " " + " ".join(words) + " "

    phrase_hits, token_hits = [], []
    for f in folders:
        fwords = _words(f.get("displayName", ""))
        if not fwords:
            continue
        if " " + " ".join(fwords) + " " in joined:
            phrase_hits.append(f)
        elif any(t in text_words for t in _key_tokens(f.get("displayName", ""))):
            token_hits.append(f)

    if len(phrase_hits) == 1:
        return phrase_hits[0]
    if not phrase_hits and len(token_hits) == 1:
        return token_hits[0]
    return None


def _load_overrides() -> dict:
    """Optional automations/piper/folder_map.json: {"Tenant name": "Folder name"}."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "folder_map.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _file_and_move(g, email: dict, portfolio_name: str) -> None:
    """Mark the message read and move it to Inbox/<portfolio>/<building>."""
    msg_id = _graph_id(email)
    if not msg_id:
        print("NOTE: no message id available; skipped read/move.")
        return

    try:
        g.mark_read(msg_id)
        print("Marked read.")
    except Exception as exc:
        print(f"WARN: mark-read failed: {exc}")

    portfolio = g.find_child_folder("inbox", portfolio_name)
    if not portfolio:
        print(f"NOTE: no '{portfolio_name}' subfolder under Inbox; left in inbox.")
        return
    overrides = _load_overrides()
    folders = g.child_folders(portfolio["id"])
    dest = _match_building_folder(email, folders, overrides)
    if not dest:
        # Fallback: some buildings (e.g. "Park 39") are filed directly under
        # Inbox rather than under portfolio.
        inbox_children = [f for f in g.child_folders("inbox") if f.get("id") != portfolio.get("id")]
        dest = _match_building_folder(email, inbox_children, overrides)
    if dest:
        try:
            g.move_message(msg_id, dest["id"])
            print(f"MOVED to folder '{dest['displayName']}'.")
        except Exception as exc:
            print(f"WARN: move failed: {exc}")
    else:
        names = ", ".join(sorted(f.get("displayName", "") for f in folders))
        print(f"No confident building-folder match; left in inbox. Add a "
              f"tenant->building override in folder_map.json. "
              f"Folders under {portfolio_name}: {names}")


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
    portfolio_name = os.environ.get("PIPER_PORTFOLIO_FOLDER", "portfolio")

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
              f"Tenant={tenant!r} date={date.today()} type={typ!r} Link={link}; "
              f"then mark read and move to the building's folder under Inbox/{portfolio_name}.")
        return 0

    g = GraphClient()
    g.add_table_row(item_path, table, row)
    print(f"ROW ADDED to {item_path}!{table}: {tenant!r} ({typ}) -> {link}")

    try:
        _file_and_move(g, email, portfolio_name)
    except Exception as exc:
        # Filing is best-effort; never fail the whole run over it.
        print(f"WARN: mark-read/move step failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
