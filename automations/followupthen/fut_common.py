"""Pure helpers for the FollowUpThen automation (no I/O — unit tested).

Kept separate from the Graph/LLM orchestration so the tricky bits (weekday
math, subject cleaning, internal-vs-external detection) are testable offline.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

FUT_DOMAINS = ("followupthen.com", "fut.io")
DEFAULT_INTERNAL_DOMAINS = ("braingroup.com",)


def weekday_bcc(now: datetime, days: int = 3, domain: str = "fut.io") -> str:
    """FollowUpThen BCC address: +``days``, snapped forward to a weekday.

    Expressed as the weekday name (fut.io resolves it to the next occurrence,
    which is always the intended day within the coming week).

        Tue -> friday@fut.io   Mon -> thursday@fut.io   Fri -> monday@fut.io
    """
    target = now + timedelta(days=days)
    wd = target.weekday()          # Mon=0 .. Sun=6
    if wd == 5:                    # Saturday -> Monday
        target += timedelta(days=2)
    elif wd == 6:                  # Sunday -> Monday
        target += timedelta(days=1)
    return f"{target.strftime('%A').lower()}@{domain}"


def clean_subject(subject: str) -> str:
    """Strip Re:/Fw:/Fwd: prefixes so the original thread can be found."""
    s = subject or ""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"^\s*(re|fw|fwd)\s*:\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def _domain(addr: str) -> str:
    m = re.search(r"@([^\s>]+)", addr or "")
    return m.group(1).lower().strip(">") if m else ""


def is_internal(addr: str, internal_domains=DEFAULT_INTERNAL_DOMAINS) -> bool:
    return _domain(addr) in {d.lower() for d in internal_domains}


def is_fut(addr: str) -> bool:
    return _domain(addr) in FUT_DOMAINS


def is_external_party(addr: str, internal_domains=DEFAULT_INTERNAL_DOMAINS) -> bool:
    """A real outside correspondent: has a domain, not internal, not FollowUpThen."""
    d = _domain(addr)
    return bool(d) and not is_internal(addr, internal_domains) and not is_fut(addr)


def pick_external_party(messages: list[dict], internal_domains=DEFAULT_INTERNAL_DOMAINS) -> str:
    """Best guess at whom we're waiting on: the most common external address."""
    counts: dict[str, int] = {}
    for m in messages:
        addrs = []
        frm = m.get("from", {}).get("emailAddress", {}).get("address", "")
        addrs.append(frm)
        for r in m.get("toRecipients", []) + m.get("ccRecipients", []):
            addrs.append(r.get("emailAddress", {}).get("address", ""))
        for a in addrs:
            if is_external_party(a, internal_domains):
                counts[a.lower()] = counts.get(a.lower(), 0) + 1
    return max(counts, key=counts.get) if counts else ""
