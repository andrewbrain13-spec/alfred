"""Core data types shared across sources, rules, and workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Attachment:
    """A single email attachment, kept in memory until a workflow saves it."""

    filename: str
    content_type: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class Message:
    """A normalized email message, independent of the source (IMAP, Graph, ...).

    Every :class:`~alfred.sources.base.EmailSource` yields these so the rule
    matcher and workflows never need to know where the mail came from.
    """

    uid: str
    """Stable per-source identifier used for de-duplication."""

    subject: str
    from_addr: str
    to_addrs: list[str]
    date: Optional[datetime]
    body_text: str
    body_html: str = ""
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def has_attachments(self) -> bool:
        return bool(self.attachments)

    def placeholders(self) -> dict[str, str]:
        """Values available for ``{subject}``-style substitution in workflows."""
        return {
            "uid": self.uid,
            "subject": self.subject,
            "from": self.from_addr,
            "to": ", ".join(self.to_addrs),
            "date": self.date.isoformat() if self.date else "",
            "body": self.body_text,
        }
