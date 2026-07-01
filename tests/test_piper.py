"""Offline tests for Piper checklist extraction, using the real sample emails."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automations.piper.append_row import _extract_link, _extract_tenant, _extract_type

SIRO = {
    "subject": "SIRO - RLC",
    "body_text": (
        "RLC Link: Renewal Lease Checklist - SIRO 2026.xlsx "
        "<https://braindevelopmentllc.sharepoint.com/:x:/s/BrainGroupSharedDrive/"
        "IQB4gHse3He-RoJ1yKt2gfWrAe1Oy5kuZLLWZ53ZtwvZmYM?e=ga3raa>\n"
        "SIRO\n3 Year Renewal\nwww.braingroup.com"
    ),
}
MISSION = {
    "subject": "NLC - Mission Kitchen & Bath",
    "body_text": (
        "New Tenant at Foxridge!\nNLC Link: New Lease Checklist - Mission K&B.xlsx "
        "<https://braindevelopmentllc.sharepoint.com/:x:/s/BrainGroupSharedDrive/"
        "IQBqtuxDCdzHQYh5zrk3PNesAQCgQzOmvTBUF4NYNLUxIrk?e=xaUmug>\n"
        "Mission Kitchen & Bath\nwww.braingroup.com"
    ),
}


def test_tenant_both_orders():
    assert _extract_tenant(SIRO) == "SIRO"
    assert _extract_tenant(MISSION) == "Mission Kitchen & Bath"


def test_type():
    assert _extract_type(SIRO) == "R"
    assert _extract_type(MISSION) == "N"


def test_link_picks_sharepoint_not_signature():
    assert _extract_link(SIRO).endswith("?e=ga3raa")
    assert "sharepoint.com" in _extract_link(MISSION)
    assert "braingroup.com" not in _extract_link(SIRO)  # signature link excluded


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
