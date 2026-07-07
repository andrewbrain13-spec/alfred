"""Offline tests for Piper checklist extraction, using the real sample emails."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automations.piper.append_row import (
    _extract_link,
    _extract_tenant,
    _extract_type,
    _match_building_folder,
)

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


def test_match_building_folder():
    folders = [
        {"id": "1", "displayName": "Foxridge Plaza"},
        {"id": "2", "displayName": "39th Street"},
        {"id": "3", "displayName": "Metcalf"},
    ]
    # Email says just "Foxridge"; folder is "Foxridge Plaza" -> token match
    assert _match_building_folder(MISSION, folders)["id"] == "1"
    # No building named -> None (won't guess)
    assert _match_building_folder(SIRO, folders) is None
    # Override maps tenant -> building folder when the email doesn't state it
    assert _match_building_folder(SIRO, folders, {"SIRO": "39th Street"})["id"] == "2"


def test_match_building_full_phrase():
    folders = [{"id": "1", "displayName": "39th Street"}, {"id": "2", "displayName": "Metcalf"}]
    email = {"subject": "NLC - Acme", "body_text": "New tenant at 39th Street this fall"}
    assert _match_building_folder(email, folders)["id"] == "1"


def test_match_building_from_html_body():
    # Real Outlook mail: body_text empty, building name only in the HTML body.
    folders = [{"id": "1", "displayName": "Metcalf Plaza"}, {"id": "2", "displayName": "Foxridge Plaza"}]
    email = {
        "subject": "NLC - NeoWellnez",
        "body_text": "",
        "body_html": "<html><body><p>New tenant at <b>Metcalf&nbsp;Plaza</b>!</p></body></html>",
    }
    assert _match_building_folder(email, folders)["id"] == "1"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
