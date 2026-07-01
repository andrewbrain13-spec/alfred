"""Track which messages have already been processed.

Without this, a poll-based source would re-run every workflow on every cycle.
State is a small JSON file mapping source name -> list of processed UIDs. We
cap the retained history so the file cannot grow without bound.
"""

from __future__ import annotations

import json
import os
from collections import deque

_MAX_REMEMBERED = 5000


class State:
    def __init__(self, path: str):
        self.path = path
        self._seen: dict[str, deque[str]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for source, uids in data.items():
                self._seen[source] = deque(uids, maxlen=_MAX_REMEMBERED)
        except (json.JSONDecodeError, OSError):
            # A corrupt state file should not stop the engine; start fresh.
            self._seen = {}

    def is_processed(self, source: str, uid: str) -> bool:
        return uid in self._seen.get(source, ())

    def mark_processed(self, source: str, uid: str) -> None:
        bucket = self._seen.setdefault(source, deque(maxlen=_MAX_REMEMBERED))
        if uid not in bucket:
            bucket.append(uid)

    def save(self) -> None:
        tmp = f"{self.path}.tmp"
        data = {source: list(uids) for source, uids in self._seen.items()}
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, self.path)  # atomic on the same filesystem
