"""POST to a webhook / web API when a message matches.

Config keys:

* ``url`` (required)  – endpoint to call. Placeholders are substituted.
* ``method`` (default POST)
* ``json``            – a dict sent as a JSON body; string values are templated.
* ``body``            – a raw string body (templated); ignored if ``json`` set.
* ``headers``         – extra request headers (dict).
* ``timeout``         – seconds (default 30).

Example (Teams/Slack-style incoming webhook):

    - type: call_webhook
      url: ${TEAMS_WEBHOOK_URL}
      json:
        text: "New match: {subject} from {from}"
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from ..models import Message
from .base import Workflow

log = logging.getLogger("alfred.call_webhook")


class CallWebhook(Workflow):
    def _render_json(self, obj: Any, message: Message) -> Any:
        if isinstance(obj, str):
            return self.render(obj, message)
        if isinstance(obj, list):
            return [self._render_json(v, message) for v in obj]
        if isinstance(obj, dict):
            return {k: self._render_json(v, message) for k, v in obj.items()}
        return obj

    def run(self, message: Message) -> None:
        url = self.spec.get("url")
        if not url:
            raise ValueError("call_webhook requires a 'url'")
        url = self.render(url, message)
        method = self.spec.get("method", "POST").upper()
        headers = self.spec.get("headers", {})
        timeout = int(self.spec.get("timeout", 30))

        kwargs: dict[str, Any] = {"headers": headers, "timeout": timeout}
        if "json" in self.spec:
            kwargs["json"] = self._render_json(self.spec["json"], message)
        elif "body" in self.spec:
            kwargs["data"] = self.render(str(self.spec["body"]), message)

        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        log.info("Webhook %s -> %s (%s)", url, resp.status_code, message.uid)
