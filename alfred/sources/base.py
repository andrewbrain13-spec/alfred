"""The EmailSource contract that every provider adapter implements."""

from __future__ import annotations

import abc
from typing import Any, Iterable

from ..models import Message


class EmailSource(abc.ABC):
    """A mailbox adapter.

    Implementations own their connection and simply yield the messages they
    consider "new". The engine handles de-duplication via :mod:`alfred.state`,
    so a source may over-report (e.g. return the last N messages each poll)
    without causing workflows to run twice.
    """

    #: Short identifier used to namespace processed-UID state.
    name: str = "source"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = config.get("name", self.name)

    @abc.abstractmethod
    def fetch_new(self) -> Iterable[Message]:
        """Return candidate new messages since the last call."""

    def close(self) -> None:
        """Release any held resources. Override if needed."""
