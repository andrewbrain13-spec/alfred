"""Microsoft Graph email source (recommended for Microsoft 365).

This is the supported, future-proof way to read an M365 mailbox: outbound
HTTPS only, no reliance on IMAP basic auth. It requires a one-time Entra
(Azure AD) app registration; see ``install/graph-setup.md``.

Two auth modes:

* ``device_code``       – delegated, for a single user's own mailbox. Great for
  an always-on personal machine: authenticate once, refresh token is cached.
* ``client_credentials`` – app-only, for unattended service accounts. Needs
  admin consent and the ``Mail.Read`` *application* permission.

This adapter uses a delta query so each poll only returns messages that are
new since the last cursor.

Dependency: ``msal`` (Microsoft Authentication Library). Install it only if you
use this source: ``pip install msal``.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

import logging

import requests

from ..models import Attachment, Message

_GRAPH = "https://graph.microsoft.com/v1.0"
log = logging.getLogger("alfred.graph_source")


class GraphSource:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = config.get("name", "graph")
        self.tenant_id = config["tenant_id"]
        self.client_id = config["client_id"]
        self.auth = config.get("auth", "device_code")
        self.client_secret = config.get("client_secret")
        self.folder = config.get("folder", "inbox")
        self.token_cache_path = config.get("token_cache", "graph_token_cache.json")
        self._delta_link: str | None = None
        self._app = None

    # -- auth ---------------------------------------------------------------
    def _acquire_token(self) -> str:
        import msal

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        if self.auth == "client_credentials":
            app = msal.ConfidentialClientApplication(
                self.client_id, authority=authority, client_credential=self.client_secret
            )
            result = app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
        else:  # device_code (delegated)
            cache = msal.SerializableTokenCache()
            if os.path.exists(self.token_cache_path):
                cache.deserialize(open(self.token_cache_path, "r", encoding="utf-8").read())
            app = msal.PublicClientApplication(
                self.client_id, authority=authority, token_cache=cache
            )
            # Same scope set as alfred.graph.GraphClient so a single consent /
            # cached token serves the source and all automations.
            from ..graph import DELEGATED_SCOPES

            scopes = [s for s in DELEGATED_SCOPES if s != "offline_access"]
            accounts = app.get_accounts()
            result = None
            if accounts:
                result = app.acquire_token_silent(scopes, account=accounts[0])
            if not result:
                flow = app.initiate_device_flow(scopes=scopes)
                print(flow["message"], flush=True)  # user visits the URL + code once
                result = app.acquire_token_by_device_flow(flow)
            if cache.has_state_changed:
                with open(self.token_cache_path, "w", encoding="utf-8") as fh:
                    fh.write(cache.serialize())

        if "access_token" not in result:
            raise RuntimeError(
                f"Graph auth failed: {result.get('error_description', result)}"
            )
        return result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._acquire_token()}"}

    # -- fetching -----------------------------------------------------------
    def fetch_new(self) -> Iterable[Message]:
        """Fetch the most recent messages in the folder; the engine dedups by id.

        Simple and robust: each poll grabs the newest `window` messages sorted
        by arrival time. New mail always lands at the top, so it is picked up on
        the next poll. Attachments are only downloaded when `fetch_attachments`
        is enabled (none of the default automations need attachment bytes).
        """
        top = int(self.config.get("window", 25))
        resp = requests.get(
            f"{_GRAPH}/me/mailFolders/{self.folder}/messages"
            f"?$top={top}&$orderby=receivedDateTime%20desc"
            "&$select=id,subject,from,toRecipients,receivedDateTime,body,hasAttachments,conversationId",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
        log.info("Graph: fetched %d recent message(s) from '%s'", len(items), self.folder)
        return [self._parse(item) for item in items]

    def _parse(self, item: dict[str, Any]) -> Message:
        from_addr = (
            item.get("from", {}).get("emailAddress", {}).get("address", "")
        )
        to_addrs = [
            r.get("emailAddress", {}).get("address", "")
            for r in item.get("toRecipients", [])
        ]
        body = item.get("body", {})
        body_html = body.get("content", "") if body.get("contentType") == "html" else ""
        body_text = body.get("content", "") if body.get("contentType") != "html" else ""

        attachments: list[Attachment] = []
        if item.get("hasAttachments") and self.config.get("fetch_attachments"):
            attachments = self._fetch_attachments(item["id"])

        from datetime import datetime

        received = item.get("receivedDateTime")
        date = None
        if received:
            try:
                date = datetime.fromisoformat(received.replace("Z", "+00:00"))
            except ValueError:
                date = None

        return Message(
            uid=f"{self.name}:{item['id']}",
            subject=item.get("subject", ""),
            from_addr=from_addr,
            to_addrs=to_addrs,
            date=date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            conversation_id=item.get("conversationId", ""),
        )

    def _fetch_attachments(self, message_id: str) -> list[Attachment]:
        import base64

        url = f"{_GRAPH}/me/messages/{message_id}/attachments"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        out = []
        for att in resp.json().get("value", []):
            content = att.get("contentBytes")
            if content:
                out.append(
                    Attachment(
                        filename=att.get("name", "attachment"),
                        content_type=att.get("contentType", "application/octet-stream"),
                        data=base64.b64decode(content),
                    )
                )
        return out

    def close(self) -> None:
        pass
