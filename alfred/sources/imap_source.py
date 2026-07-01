"""IMAP email source.

Fastest path to a working setup: no cloud app registration, just an IMAP host
and credentials. For Microsoft 365 the host is ``outlook.office365.com``.

Auth options:

* ``password`` – a mailbox password or, on M365, an *app password*. Requires
  the tenant to permit IMAP basic auth (many tenants disable this — if login
  fails with AUTHENTICATE errors, switch to the Graph source instead).
* ``xoauth2``  – an OAuth2 access token (advanced; token acquisition is left
  to you / a future helper). Set ``auth: xoauth2`` and provide ``token``.

The source polls: each call fetches recent messages in the target folder and
yields them. De-duplication happens in the engine via message UID, so polling
overlap is harmless.
"""

from __future__ import annotations

import email
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

from imapclient import IMAPClient

from ..models import Attachment, Message


def _decode(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except Exception:
        return str(value)


class ImapSource:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = config.get("name", "imap")
        self.host = config["host"]
        self.port = int(config.get("port", 993))
        self.username = config["username"]
        self.folder = config.get("folder", "INBOX")
        self.auth = config.get("auth", "password")
        self.password = config.get("password")
        self.token = config.get("token")
        # How many recent messages to inspect per poll. The engine skips any
        # already-processed UID, so this is just a safety window, not a limit
        # on how many can be handled over time.
        self.window = int(config.get("window", 25))
        self._client: IMAPClient | None = None

    def _connect(self) -> IMAPClient:
        client = IMAPClient(self.host, port=self.port, ssl=True)
        if self.auth == "xoauth2":
            client.oauth2_login(self.username, self.token)
        else:
            client.login(self.username, self.password)
        client.select_folder(self.folder)
        return client

    def _ensure_client(self) -> IMAPClient:
        if self._client is None:
            self._client = self._connect()
        return self._client

    def fetch_new(self) -> Iterable[Message]:
        try:
            client = self._ensure_client()
            uids = client.search(["ALL"])
        except Exception:
            # Reconnect once on any connection hiccup, then re-raise if it fails.
            self.close()
            client = self._ensure_client()
            uids = client.search(["ALL"])

        recent = sorted(uids)[-self.window :]
        if not recent:
            return []

        fetched = client.fetch(recent, ["RFC822"])
        messages = []
        for uid in recent:
            raw = fetched.get(uid, {}).get(b"RFC822")
            if raw:
                messages.append(self._parse(uid, raw))
        return messages

    def _parse(self, uid: int, raw: bytes) -> Message:
        msg = email.message_from_bytes(raw)
        subject = _decode(msg.get("Subject"))
        from_addr = _decode(msg.get("From"))
        to_addrs = [a.strip() for a in _decode(msg.get("To")).split(",") if a.strip()]
        try:
            date = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
        except (TypeError, ValueError):
            date = None

        body_text, body_html, attachments = "", "", []
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = str(part.get("Content-Disposition") or "")
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            if "attachment" in disposition or part.get_filename():
                attachments.append(
                    Attachment(
                        filename=_decode(part.get_filename()) or "attachment",
                        content_type=content_type,
                        data=payload,
                    )
                )
            elif content_type == "text/plain" and not body_text:
                body_text = payload.decode(part.get_content_charset() or "utf-8", "replace")
            elif content_type == "text/html" and not body_html:
                body_html = payload.decode(part.get_content_charset() or "utf-8", "replace")

        return Message(
            uid=f"{self.name}:{uid}",
            subject=subject,
            from_addr=from_addr,
            to_addrs=to_addrs,
            date=date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.logout()
            except Exception:
                pass
            self._client = None
