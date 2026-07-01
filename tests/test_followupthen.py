"""Offline tests for FollowUpThen date/subject/party logic."""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automations.followupthen.fut_common import (
    clean_subject,
    is_external_party,
    pick_external_party,
    weekday_bcc,
)


def test_weekday_bcc_examples():
    # 2026-06-30 is a Tuesday -> +3 = Friday
    assert weekday_bcc(datetime(2026, 6, 30, 6, 0)) == "friday@fut.io"
    # 2026-06-29 is a Monday -> +3 = Thursday
    assert weekday_bcc(datetime(2026, 6, 29, 6, 0)) == "thursday@fut.io"
    # 2026-07-03 is a Friday -> +3 = Monday (weekday, no snap)
    assert weekday_bcc(datetime(2026, 7, 3, 6, 0)) == "monday@fut.io"


def test_weekday_bcc_snaps_weekend_to_monday():
    # 2026-07-01 Wednesday -> +3 = Saturday -> snap to Monday
    assert weekday_bcc(datetime(2026, 7, 1, 6, 0)) == "monday@fut.io"
    # 2026-07-02 Thursday -> +3 = Sunday -> snap to Monday
    assert weekday_bcc(datetime(2026, 7, 2, 6, 0)) == "monday@fut.io"


def test_clean_subject():
    assert clean_subject("Re: Fwd: RE:  Contract renewal") == "Contract renewal"
    assert clean_subject("Proposal") == "Proposal"


def test_external_detection():
    assert is_external_party("jane@clientco.com")
    assert not is_external_party("me@braingroup.com")
    assert not is_external_party("mondayat6am@followupthen.com")
    assert not is_external_party("noreply@fut.io")


def test_pick_external_party():
    msgs = [
        {"from": {"emailAddress": {"address": "me@braingroup.com"}},
         "toRecipients": [{"emailAddress": {"address": "jane@clientco.com"}}],
         "ccRecipients": []},
        {"from": {"emailAddress": {"address": "colleague@braingroup.com"}},
         "toRecipients": [{"emailAddress": {"address": "jane@clientco.com"}}],
         "ccRecipients": []},
    ]
    assert pick_external_party(msgs) == "jane@clientco.com"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
