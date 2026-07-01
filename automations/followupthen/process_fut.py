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

    g = GraphClient()

    # 1. Find the original thread by subject (excluding FollowUpThen's own mail).
    candidates = [
        m for m in g.search_messages(f"subject:{subject}", top=25)
        if not m.get("isDraft") and not is_fut(m.get("from", {}).get("emailAddress", {}).get("address", ""))
    ]
    if not candidates:
        print(f"SKIPPED: no Outlook thread found for subject {subject!r}.")
        return 0
    candidates.sort(key=lambda m: m.get("receivedDateTime", ""), reverse=True)
    conversation_id = candidates[0]["conversationId"]
    thread = g.get_conversation(conversation_id) or candidates

    # 2. Judge.
    verdict = _judge_external_reply(_transcript(thread), internal)
    print(f"JUDGMENT: {verdict}")
    if verdict.get("external_reply"):
        print("SKIPPED: meaningful external reply present; no nudge needed.")
        return 0

    # 3. Compose the draft.
    waiting_on = verdict.get("waiting_on") or pick_external_party(thread, internal)
    if not waiting_on:
        print("SKIPPED: could not identify an external party to nudge.")
        return 0
    bcc = weekday_bcc(datetime.now())
    reply_to_id = thread[-1]["id"]  # latest message in the thread

    if dry_run:
        print(f"DRY-RUN: would draft reply to {waiting_on}, BCC {bcc}, "
              f"body {nudge!r}, in thread {subject!r}.")
        return 0

    draft = g.create_reply_draft(reply_to_id)
    g.update_message(draft["id"], {
        "toRecipients": [{"emailAddress": {"address": waiting_on}}],
        "bccRecipients": [{"emailAddress": {"address": bcc}}],
        "body": {"contentType": "text", "content": nudge},
    })
    print(f"DRAFT CREATED: to {waiting_on}, BCC {bcc}, thread {subject!r}. "
          f"Review in Outlook Drafts and click Send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
