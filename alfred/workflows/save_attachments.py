"""Save a matched message's attachments (and optionally its body) to disk.

Config keys:

* ``dir`` (required) – destination directory. Placeholders are substituted, so
  you can route by sender/subject, e.g. ``C:/Alfred/{from}``.
* ``pattern``  – filename regex; only attachments whose name matches are saved.
* ``save_body`` (default false) – also write the plain-text body as a .txt file.
* ``overwrite`` (default false) – overwrite existing files instead of
  uniquifying with a numeric suffix.
"""

from __future__ import annotations

import logging
import os
import re

from ..models import Message
from .base import Workflow

log = logging.getLogger("alfred.save_attachments")

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_name(name: str) -> str:
    return _UNSAFE.sub("_", name).strip() or "attachment"


class SaveAttachments(Workflow):
    def _unique(self, path: str) -> str:
        if self.spec.get("overwrite") or not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        return f"{base}_{i}{ext}"

    def run(self, message: Message) -> None:
        directory = self.spec.get("dir")
        if not directory:
            raise ValueError("save_attachments requires a 'dir'")
        directory = _safe_name_path(self.render(directory, message))
        os.makedirs(directory, exist_ok=True)

        pattern = self.spec.get("pattern")
        compiled = re.compile(pattern, re.IGNORECASE) if pattern else None

        saved = 0
        for att in message.attachments:
            if compiled and not compiled.search(att.filename):
                continue
            dest = self._unique(os.path.join(directory, _safe_name(att.filename)))
            with open(dest, "wb") as fh:
                fh.write(att.data)
            saved += 1
            log.info("Saved attachment %s (%s)", dest, message.uid)

        if self.spec.get("save_body"):
            dest = self._unique(os.path.join(directory, f"{_safe_name(message.subject)}.txt"))
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(message.body_text)
            log.info("Saved body %s (%s)", dest, message.uid)

        if saved == 0 and not self.spec.get("save_body"):
            log.info("No matching attachments to save (%s)", message.uid)


def _safe_name_path(path: str) -> str:
    """Sanitize each path component but keep separators and a drive letter."""
    drive, rest = os.path.splitdrive(path)
    parts = re.split(r"[\\/]", rest)
    cleaned = [_UNSAFE.sub("_", p) if p not in ("", ".", "..") else p for p in parts]
    return drive + os.sep.join(cleaned)
