"""Match a message against the rule table and run the resulting workflows."""

from __future__ import annotations

import logging

from . import rules
from .config import RuleConfig
from .models import Message
from .workflows import build_workflow

log = logging.getLogger("alfred.dispatcher")


class Dispatcher:
    def __init__(self, rule_configs: list[RuleConfig]):
        self.rule_configs = rule_configs
        # Fail fast on unknown workflow types by constructing them up front.
        self._workflows = {
            rc.name: [build_workflow(spec) for spec in rc.workflows]
            for rc in rule_configs
        }

    def dispatch(self, message: Message) -> int:
        """Run every matching rule's workflows. Returns how many rules matched."""
        matched = 0
        for rc in self.rule_configs:
            if not rules.matches(rc.match, message):
                continue
            matched += 1
            log.info("Rule %r matched message %s (%r)", rc.name, message.uid, message.subject)
            for wf in self._workflows[rc.name]:
                try:
                    wf.run(message)
                except Exception as exc:  # isolate: one failure never stops the rest
                    log.exception("Workflow %s failed for %s: %s", wf.spec.get("type"), message.uid, exc)
            if rc.stop_on_match:
                break
        return matched
