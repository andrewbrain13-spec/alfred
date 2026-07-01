"""Workflows: the pluggable actions run when a rule's trigger matches.

Register a new workflow by adding it to ``REGISTRY`` below; the ``type`` key in
a rule's ``workflows`` list selects which one to run.
"""

from __future__ import annotations

from typing import Any

from .base import Workflow
from .call_webhook import CallWebhook
from .claude_agent import ClaudeAgent
from .run_command import RunCommand
from .save_attachments import SaveAttachments
from .send_reply import SendReply

REGISTRY: dict[str, type[Workflow]] = {
    "run_command": RunCommand,
    "call_webhook": CallWebhook,
    "send_reply": SendReply,
    "save_attachments": SaveAttachments,
    "claude_agent": ClaudeAgent,
}


def build_workflow(spec: dict[str, Any]) -> Workflow:
    wf_type = spec.get("type")
    if wf_type not in REGISTRY:
        raise ValueError(
            f"Unknown workflow type {wf_type!r}. Known: {', '.join(sorted(REGISTRY))}"
        )
    return REGISTRY[wf_type](spec)
