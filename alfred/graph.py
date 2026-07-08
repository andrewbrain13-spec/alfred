"""Shared Microsoft Graph client for automations (mail drafts, Excel, files).

Reuses the same Entra app registration and delegated auth as the Graph email
source, so a single one-time device-code sign-in (cached token) covers reading
mail, creating drafts, and editing the OneDrive workbook. It deliberately does
NOT request Mail.Send — automations only ever create drafts you send yourself.

Env vars:
  ALFRED_TENANT_ID, ALFRED_CLIENT_ID   – from the app registration
  GRAPH_TOKEN_CACHE (optional)         – token cache path (default graph_token_cache.json)
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

import requests

GRAPH = "https://graph.microsoft.com/v1.0"

# One consented scope set for every automation. Mail.ReadWrite covers reading
# threads and creating/updating drafts (but not sending); Files.ReadWrite covers
# the OneDrive tracking workbook.
DELEGATED_SCOPES = ["Mail.ReadWrite", "Files.ReadWrite", "offline_access"]


class GraphClient:
    def __init__(self, tenant_id: str | None = None, client_id: str | None = None,
                 token_cache: str | None = None):
        self.tenant_id = tenant_id or os.environ["ALFRED_TENANT_ID"]
        self.client_id = client_id or os.environ["ALFRED_CLIENT_ID"]
        self.token_cache = token_cache or os.environ.get(
            "GRAPH_TOKEN_CACHE", "graph_token_cache.json"
        )

    # -- auth ---------------------------------------------------------------
    def _token(self) -> str:
        import msal

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache):
            cache.deserialize(open(self.token_cache, "r", encoding="utf-8").read())
        app = msal.PublicClientApplication(self.client_id, authority=authority, token_cache=cache)
        scopes = [s for s in DELEGATED_SCOPES if s != "offline_access"]
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])
        if not result:
            flow = app.initiate_device_flow(scopes=scopes)
            print(flow["message"], flush=True)
            result = app.acquire_token_by_device_flow(flow)
        if cache.has_state_changed:
            with open(self.token_cache, "w", encoding="utf-8") as fh:
                fh.write(cache.serialize())
        if "access_token" not in result:
            raise RuntimeError(f"Graph auth failed: {result.get('error_description', result)}")
        return result["access_token"]

    def request(self, method: str, path_or_url: str, **kwargs) -> requests.Response:
        url = path_or_url if path_or_url.startswith("http") else GRAPH + path_or_url
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token()}"
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    # -- mail ---------------------------------------------------------------
    def search_messages(self, query: str, top: int = 25) -> list[dict]:
        # $search needs the ConsistencyLevel header. URL-encode the quoted
        # phrase so subjects with & / - / : don't break the URL or the query.
        q = quote(f'"{query}"', safe="")
        resp = self.request(
            "GET",
            f"/me/messages?$search={q}&$top={top}"
            "&$select=id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
            "conversationId,bodyPreview,isDraft",
            headers={"ConsistencyLevel": "eventual"},
        )
        return resp.json().get("value", [])

    def get_conversation(self, conversation_id: str) -> list[dict]:
        # Graph rejects $orderby combined with a conversationId $filter, and the
        # id contains URL-unsafe characters — encode the value and sort locally.
        cid = quote(conversation_id, safe="")
        resp = self.request(
            "GET",
            f"/me/messages?$filter=conversationId eq '{cid}'&$top=50"
            "&$select=id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
            "bodyPreview,isDraft",
        )
        msgs = resp.json().get("value", [])
        msgs.sort(key=lambda m: m.get("receivedDateTime", ""))
        return msgs

    def create_reply_draft(self, message_id: str) -> dict:
        """Create a draft reply in the Drafts folder (does not send)."""
        return self.request("POST", f"/me/messages/{quote(message_id, safe='')}/createReply").json()

    def update_message(self, message_id: str, patch: dict[str, Any]) -> dict:
        return self.request("PATCH", f"/me/messages/{quote(message_id, safe='')}", json=patch).json()

    def mark_read(self, message_id: str) -> dict:
        return self.update_message(message_id, {"isRead": True})

    def move_message(self, message_id: str, destination_id: str) -> dict:
        return self.request(
            "POST", f"/me/messages/{quote(message_id, safe='')}/move",
            json={"destinationId": destination_id},
        ).json()

    # -- folders ------------------------------------------------------------
    def child_folders(self, parent_id: str) -> list[dict]:
        """All child folders of a folder (well-known name like 'inbox' or an id)."""
        url = f"/me/mailFolders/{parent_id}/childFolders?$top=100&$select=id,displayName"
        out: list[dict] = []
        while url:
            data = self.request("GET", url).json()
            out += data.get("value", [])
            url = data.get("@odata.nextLink")
        return out

    def find_child_folder(self, parent_id: str, name: str) -> dict | None:
        for f in self.child_folders(parent_id):
            if (f.get("displayName") or "").strip().lower() == name.strip().lower():
                return f
        return None

    # -- excel --------------------------------------------------------------
    def add_table_row(self, item_path: str, table: str, values: list[Any]) -> dict:
        """Append one row to a workbook table by drive-relative item path."""
        norm = [_excel_cell(v) for v in values]
        return self.request(
            "POST",
            f"/me/drive/root:/{quote(item_path, safe='/')}:/workbook/tables/{table}/rows",
            json={"index": None, "values": [norm]},
        ).json()


def _excel_cell(value: Any) -> Any:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        # Excel serial date so the column's date format renders it correctly.
        return (value - date(1899, 12, 30)).days
    return value
