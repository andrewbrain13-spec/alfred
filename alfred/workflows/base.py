"""Base class and shared helpers for workflows."""

from __future__ import annotations

import abc
from typing import Any

from ..models import Message


class Workflow(abc.ABC):
    """A single action taken in response to a matched message."""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec

    @abc.abstractmethod
    def run(self, message: Message) -> None:
        """Perform the action. Raising propagates to the engine, which logs it
        and continues with the next workflow — one failure never aborts the run."""

    def render(self, template: str, message: Message) -> str:
        """Substitute ``{subject}``/``{from}``/... placeholders from the message.

        Unknown placeholders are left untouched rather than raising, so a
        stray brace in config can't crash a workflow.
        """
        class _Safe(dict):
            def __missing__(self, key):  # noqa: D401
                return "{" + key + "}"

        return template.format_map(_Safe(message.placeholders()))
