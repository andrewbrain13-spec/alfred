#!/usr/bin/env python3
"""Automation #3: handle a FollowUpThen reminder.

Flow (all safe — only ever creates a DRAFT, never sends):
  1. A FollowUpThen reminder lands (matched by Alfred, passed here as JSON).
  2. Find the original Outlook thread by its subject.
  3. Ask Claude to judge: has an EXTERNAL party sent a meaningful reply since we
     last wrote (not internal chatter, not an auto-reply)?
  4. If NOT, create a draft reply to that external party in the thread, with the
     nudge text and a BCC to the FollowUpThen weekday address (so when you click
     Send, the next reminder is scheduled). You review and send.

Env:
  ALFRED_MESSAGE_JSON     path to the reminder email JSON (set by Alfred)
  ALFRED_DRY_RUN          "1" = log only, don't touch the mailbox (default "1")
  ALFRED_TENANT_ID / ALFRED_CLIENT_ID   Graph app registration
  FUT_INTERNAL_DOMAINS    comma list; default "braingroup.com"
  FUT_NUDGE_BODY          draft body; default "Any update on this?"
  CLAUDE_BIN              path to Claude Code CLI (default "claude")
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from alfred.graph import GraphClient
from automations.followupthen.fut_common import (
    clean_subject,
    is_fut,
    pick_external_party,
    weekday_bcc,
)


def _load_reminder() -> dict:
    path = os.environ.get("ALFRED_MESSAGE_JSON")
    if path and os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return json.loads(sys.stdin.read() or "{}")


def extract_fut_target(reminder: dict) -> str:
    """FollowUpThen states whom to follow up with: 'Time to followup with X'.

    Reading it from the reminder is more reliable than inferring from the thread.
    """
    text = f"{reminder.get('body_text','')}\n{reminder.get('body_html','')}"
    m = re.search(
        r"follow\s*up\s+with\s+([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
        text, re.IGNORECASE,
    )
    return m.group(1).lower() if m else ""


def _judge_external_reply(transcript: str, internal_domains: list[str]) -> dict:
    """Ask Claude whether there's a meaningful external reply. Returns a dict."""
    prompt = (
        "You are analyzing an email thread to decide whether we are still "
        "waiting on the other party.\n"
        f"Our internal domains: {', '.join(internal_domains)}. Anyone else is "
        "external.\n\n"
        "A 'meaningful external reply' is a substantive response from an EXTERNAL "
        "participant that came AFTER our most recent outbound message. It does NOT "
        "include: internal-only discussion, auto-replies/out-of-office, read "
        "receipts, or mere acknowledgements.\n\n"
        "Thread (oldest first):\n" + transcript + "\n\n"
        "Respond with ONLY a JSON object: "
        '{"external_reply": true|false, "waiting_on": "<external email or empty>", '
        '"reason": "<one sentence>"}'
    )
    bin_ = os.environ.get("CLAUDE_BIN", "claude")
    out = subprocess.run(
        [bin_, "-p", prompt, "--output-format", "text"],
        capture_output=True, text=True, timeout=300,
    )
    if out.returncode != 0:
        raise RuntimeError(f"Claude judgment failed: {out.stderr.strip()[:300]}")
    m = re.search(r"\{.*\}", out.stdout, re.DOTALL)
    if not m:
        raise RuntimeError(f"Could not parse judgment JSON from: {out.stdout[:300]}")
    return json.loads(m.group(0))


def _html_escape(s: str) -> str:
    return ((s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\n", "<br>"))


def _insert_into_body(html: str, insert: str) -> str:
    """Insert our content just after <body> (or at the top if there's no body tag)."""
    m = re.search(r"<body[^>]*>", html, re.IGNORECASE)
    if m:
        return html[:m.end()] + insert + html[m.end():]
    return insert + html


def _extract_body(html: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else html


def _inline_images(html: str, base_dir: str) -> str:
    """Rewrite relative <img src> to data: URIs so a signature's logo renders."""
    import base64
    import mimetypes
    import urllib.parse

    def repl(m):
        src = m.group(1)
        if src.startswith(("data:", "http:", "https:", "cid:")):
            return m.group(0)
        path = os.path.join(base_dir, urllib.parse.unquote(src).replace("/", os.sep))
        if os.path.exists(path):
            mime = mimetypes.guess_type(path)[0] or "image/png"
            data = base64.b64encode(open(path, "rb").read()).decode("ascii")
            return m.group(0).replace(src, f"data:{mime};base64,{data}")
        return m.group(0)

    return re.sub(r'src="([^"]+)"', repl, html)


def _load_signature_html() -> str:
    """The user's Outlook signature as inline HTML (with images embedded).

    Uses FUT_SIGNATURE_FILE if set; otherwise auto-detects from the Outlook
    Signatures folder (FUT_SIGNATURE_NAME picks one when there are several).
    Returns '' if none is found — a draft without a signature is still fine.
    """
    try:
        chosen = os.environ.get("FUT_SIGNATURE_FILE")
        if not (chosen and os.path.exists(chosen)):
            chosen = None
            appdata = os.environ.get("APPDATA")
            sigdir = os.path.join(appdata, "Microsoft", "Signatures") if appdata else None
            if sigdir and os.path.isdir(sigdir):
                htms = [os.path.join(sigdir, f) for f in os.listdir(sigdir)
                        if f.lower().endswith(".htm")]
                name = os.environ.get("FUT_SIGNATURE_NAME")
                if name:
                    chosen = next((h for h in htms if name.lower() in os.path.basename(h).lower()), None)
                if not chosen and len(htms) == 1:
                    chosen = htms[0]
                elif not chosen and htms:
                    chosen = max(htms, key=os.path.getmtime)
        if not chosen or not os.path.exists(chosen):
            return ""
        raw = open(chosen, "rb").read()
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("cp1252", "replace")
        html = _inline_images(_extract_body(html), os.path.dirname(chosen))
        return "<br>" + html
    except Exception:
        return ""


def _has_participant(message: dict, addr: str) -> bool:
    """True if `addr` is the sender or a recipient of the message."""
    if not addr:
        return False
    people = [message.get("from", {}).get("emailAddress", {}).get("address", "")]
    for r in message.get("toRecipients", []) + message.get("ccRecipients", []):
        people.append(r.get("emailAddress", {}).get("address", ""))
    return any(addr.lower() == p.lower() for p in people if p)


def _transcript(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        if m.get("isDraft"):
            continue
        frm = m.get("from", {}).get("emailAddress", {}).get("address", "?")
        when = m.get("receivedDateTime", "?")
        preview = (m.get("bodyPreview", "") or "").replace("\n", " ")[:300]
        lines.append(f"[{when}] {frm}: {preview}")
    return "\n".join(lines)


def main() -> int:
    dry_run = os.environ.get("ALFRED_DRY_RUN", "1") == "1"
    internal = [d.strip() for d in os.environ.get("FUT_INTERNAL_DOMAINS", "braingroup.com").split(",") if d.strip()]
    nudge = os.environ.get("FUT_NUDGE_BODY", "Any update on this?")

    reminder = _load_reminder()
    subject = clean_subject(reminder.get("subject", ""))
    if not subject:
        print("SKIPPED: reminder has no usable subject.")
        return 0
    fut_target = extract_fut_target(reminder)  # whom FollowUpThen says to nudge
    print(f"THREAD: {subject!r}  FUT target: {fut_target or '(not stated)'}")

    g = GraphClient()

    # 1. Find the original thread by subject (excluding FollowUpThen's own mail
    #    and our own drafts). Prefer a thread the follow-up target is part of.
    #    Strip punctuation so the keyword search stays valid (KQL treats '-'/':'
    #    specially and '&' would break the URL).
    search_terms = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]+", " ", subject)).strip()
    if not search_terms:
        print(f"SKIPPED: subject {subject!r} has no searchable terms.")
        return 0
    candidates = [
        m for m in g.search_messages(search_terms, top=25)
        if not m.get("isDraft") and not is_fut(m.get("from", {}).get("emailAddress", {}).get("address", ""))
    ]
    if not candidates:
        print(f"SKIPPED: no Outlook thread found for subject {subject!r}.")
        return 0
    candidates.sort(key=lambda m: m.get("receivedDateTime", ""), reverse=True)
    with_target = [m for m in candidates if fut_target and _has_participant(m, fut_target)]
    chosen = (with_target or candidates)[0]
    conversation_id = chosen.get("conversationId")

    try:
        thread = g.get_conversation(conversation_id) if conversation_id else []
    except Exception as exc:
        print(f"NOTE: thread lookup failed ({exc}); using subject-match results.")
        thread = []
    # Keep only real messages (no drafts, no FollowUpThen), oldest->newest.
    thread = [
        m for m in (thread or candidates)
        if not m.get("isDraft") and not is_fut(m.get("from", {}).get("emailAddress", {}).get("address", ""))
    ] or candidates

    # 2. Judge.
    verdict = _judge_external_reply(_transcript(thread), internal)
    print(f"JUDGMENT: {verdict}")
    if verdict.get("external_reply"):
        print("SKIPPED: meaningful external reply present; no nudge needed.")
        return 0

    # 3. Compose the draft. FollowUpThen's stated target wins; then the
    #    judgment's guess; then the most common external party in the thread.
    waiting_on = fut_target or verdict.get("waiting_on") or pick_external_party(thread, internal)
    if not waiting_on:
        print("SKIPPED: could not identify an external party to nudge.")
        return 0
    bcc = weekday_bcc(datetime.now())
    reply_to_id = thread[-1]["id"]  # latest real message in the original thread

    if dry_run:
        print(f"DRY-RUN: would draft reply to {waiting_on}, BCC {bcc}, "
              f"body {nudge!r}, in thread {subject!r}.")
        return 0

    draft = g.create_reply_draft(reply_to_id)
    draft_id = draft["id"]

    # Keep the quoted conversation that createReply produced; insert the nudge
    # (and the signature) at the top, like a normal reply.
    body = g.get_message(draft_id, select="body").get("body", {})
    original = body.get("content", "")
    ctype = (body.get("contentType") or "html").lower()
    top = f"<p>{_html_escape(nudge)}</p>" + _load_signature_html()
    if ctype == "html" and original:
        new_content = _insert_into_body(original, top)
    else:
        new_content = top + (f"<br><br>{_html_escape(original)}" if original else "")

    g.update_message(draft_id, {
        "toRecipients": [{"emailAddress": {"address": waiting_on}}],
        "bccRecipients": [{"emailAddress": {"address": bcc}}],
        "body": {"contentType": "HTML", "content": new_content},
    })
    print(f"DRAFT CREATED: to {waiting_on}, BCC {bcc}, thread {subject!r} "
          f"(quoted thread + signature preserved). Review in Outlook Drafts and Send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
