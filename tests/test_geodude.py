"""Offline tests for Geodude batch grouping / date logic."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automations.geodude.send_daily import (
    _summary_name,
    extract_date_token,
    format_subject_date,
    group_by_date,
)

BATCH = [
    # Real files use hyphenated dates; keep a non-hyphenated one to prove both work.
    "Geodude_Summary_2026-07-10.docx",
    "Geodude_Screen_2026-07-10.xlsx",
    "Geodude_Model_157910_2026-07-10.xlsx",
    "Geodude_Model_158102_2026-07-10.xlsx",
    "Geodude_Model_157914_20260710.xlsx",   # non-hyphenated, same batch
    "Geodude_Model_v7_TEMPLATE.xlsx",       # no date -> ignored
    "geodude_model_v7.py",                   # no date -> ignored
    "EnergyNet_Lots_Model_Run_2026-07-03.xlsx",  # not "geodude" -> ignored
    "Geodude_Summary_2026-07-11.docx",       # next day
]


def test_extract_date_token():
    assert extract_date_token("Geodude_Model_157910_2026-07-10.xlsx") == "20260710"
    assert extract_date_token("Geodude_Summary_20260710.docx") == "20260710"
    assert extract_date_token("Geodude_Model_v7_TEMPLATE.xlsx") == ""
    assert extract_date_token("random.txt") == ""


def test_group_by_date():
    groups = group_by_date(BATCH)
    assert set(groups) == {"20260710", "20260711"}
    assert len(groups["20260710"]) == 5           # 4 hyphenated + 1 non-hyphenated
    assert "Geodude_Model_v7_TEMPLATE.xlsx" not in groups.get("20260710", [])


def test_summary_name():
    assert _summary_name(BATCH[:5]) == "Geodude_Summary_2026-07-10.docx"
    assert _summary_name(["Geodude_Screen_2026-07-10.xlsx"]) is None


def test_format_subject_date():
    assert format_subject_date("20260710") == "July 10, 2026"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
