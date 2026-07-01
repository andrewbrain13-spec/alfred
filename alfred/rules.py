"""Trigger matching: decide whether a message satisfies a rule's conditions.

A rule's ``match`` block is a dict of conditions that are ANDed together. All
supported conditions:

* ``subject``        – regex searched against the subject
* ``from``           – regex searched against the sender address
* ``to``             – regex searched against any recipient
* ``body``           – regex searched against the plain-text body
* ``has_attachment`` – bool; require (or forbid) attachments

Text conditions are regular expressions (case-insensitive). A plain word like
``invoice`` works as a substring match; use anchors/character classes for more
precision, e.g. ``^\\[ALERT\\]`` or ``@vendor\\.com$``.
"""

from __future__ import annotations

import re
from typing import Any

from .models import Message


def _regex_matches(pattern: str, *haystacks: str) -> bool:
    compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
    return any(compiled.search(h or "") for h in haystacks)


def matches(match_block: dict[str, Any], message: Message) -> bool:
    """Return True only if every condition in ``match_block`` holds."""
    if not match_block:
        return False  # an empty match block would fire on everything; require intent

    for key, expected in match_block.items():
        if key == "subject":
            if not _regex_matches(str(expected), message.subject):
                return False
        elif key == "from":
            if not _regex_matches(str(expected), message.from_addr):
                return False
        elif key == "to":
            if not _regex_matches(str(expected), *message.to_addrs):
                return False
        elif key == "body":
            if not _regex_matches(str(expected), message.body_text):
                return False
        elif key == "has_attachment":
            if bool(expected) != message.has_attachments:
                return False
        else:
            raise ValueError(f"Unknown match condition: {key!r}")

    return True
