"""Offline smoke tests — exercise matching, dispatch, and dedup without a mailbox.

Run with:  python -m pytest tests/   (or)   python tests/test_engine.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alfred import rules
from alfred.config import RuleConfig
from alfred.dispatcher import Dispatcher
from alfred.models import Message


def _msg(**kw) -> Message:
    base = dict(
        uid="test:1",
        subject="Weekly Invoice #42",
        from_addr="billing@somevendor.com",
        to_addrs=["abrain@braingroup.com"],
        date=None,
        body_text="Please find attached.",
    )
    base.update(kw)
    return Message(**base)


def test_subject_and_from_match():
    block = {"subject": "invoice", "from": "@somevendor\\.com"}
    assert rules.matches(block, _msg())
    assert not rules.matches(block, _msg(subject="Lunch?"))
    assert not rules.matches(block, _msg(from_addr="friend@gmail.com"))


def test_empty_match_never_fires():
    assert not rules.matches({}, _msg())


def test_has_attachment_condition():
    from alfred.models import Attachment

    assert not rules.matches({"has_attachment": True}, _msg())
    with_att = _msg(attachments=[Attachment("a.pdf", "application/pdf", b"x")])
    assert rules.matches({"has_attachment": True}, with_att)


def test_dispatch_runs_matching_workflow(tmp_path=None):
    ran = {}

    # A tiny in-process workflow via the registry.
    from alfred.workflows import REGISTRY
    from alfred.workflows.base import Workflow

    class Record(Workflow):
        def run(self, message):
            ran["subject"] = message.subject

    REGISTRY["_record"] = Record
    try:
        d = Dispatcher([
            RuleConfig(name="r", match={"subject": "invoice"}, workflows=[{"type": "_record"}])
        ])
        assert d.dispatch(_msg()) == 1
        assert ran["subject"] == "Weekly Invoice #42"
        # Non-matching message runs nothing.
        ran.clear()
        assert d.dispatch(_msg(subject="hello")) == 0
        assert not ran
    finally:
        REGISTRY.pop("_record", None)


def test_workflow_failure_is_isolated():
    from alfred.workflows import REGISTRY
    from alfred.workflows.base import Workflow

    order = []

    class Boom(Workflow):
        def run(self, message):
            order.append("boom")
            raise RuntimeError("kaboom")

    class After(Workflow):
        def run(self, message):
            order.append("after")

    REGISTRY["_boom"] = Boom
    REGISTRY["_after"] = After
    try:
        d = Dispatcher([
            RuleConfig(
                name="r",
                match={"subject": "invoice"},
                workflows=[{"type": "_boom"}, {"type": "_after"}],
            )
        ])
        d.dispatch(_msg())
        assert order == ["boom", "after"]  # failure didn't stop the next workflow
    finally:
        REGISTRY.pop("_boom", None)
        REGISTRY.pop("_after", None)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
