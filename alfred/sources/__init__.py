"""Email sources: the pluggable adapters that yield new :class:`Message`s."""

from __future__ import annotations

from typing import Any

from .base import EmailSource


def build_source(config: dict[str, Any]) -> EmailSource:
    """Instantiate the source named by ``config['type']``."""
    source_type = config.get("type")
    if source_type == "imap":
        from .imap_source import ImapSource

        return ImapSource(config)
    if source_type == "graph":
        from .graph_source import GraphSource

        return GraphSource(config)
    raise ValueError(
        f"Unknown source type {source_type!r}. Supported: 'imap', 'graph'."
    )
