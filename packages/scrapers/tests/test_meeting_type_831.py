"""#831: the meeting type a video title names. Pure logic, no database."""

from __future__ import annotations

import pytest
from scrapers.youtube import meeting_type as mt


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # what the old six checks already answered: unchanged
        ("Tuscaloosa City Council Meeting", "City Council"),
        ("Council Meeting 5/12/26", "City Council"),
        ("City Council Work Session", "City Council"),
        ("Planning and Zoning Commission Meeting", "Planning Commission"),
        ("Zoning Board of Adjustment", "Planning Commission"),
        ("School Board Regular Meeting", "School Board"),
        ("Board of Education Work Session", "School Board"),
        ("Special Called Meeting", "Special Meeting"),
        ("Budget Workshop", "Workshop"),
        # the titles from #829 that were stored as Other
        ("Tuscaloosa Finance Committee Meeting", "Committee"),
        ("Tuscaloosa Projects Committee Meeting", "Committee"),
        ("Tuscaloosa Historic Preservation Commission Meeting", "Commission"),
        ("Tuscaloosa Capital Projects Work Session", "Work Session"),
        ("Tuscaloosa Pre-Council Briefing", "Briefing"),
        # other bodies and forms
        ("County Commissioners Regular Session", "Commission"),
        ("Library Board of Trustees", "Board"),
        ("Housing Authority monthly meeting", "Authority"),
        ("Public Hearing on the FY27 Budget", "Public Hearing"),
        ("District 1 Town Hall", "Town Hall"),
        ("WORKSESSION 5/12", "Work Session"),
        ("Youth Council swearing-in", "Council"),
    ],
)
def test_meeting_type_from_title(title, expected):
    assert mt.meeting_type_from_title(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Clayton County Celebrating 5 Splash-tastic Years Spivey Splash Water Park Opens",
        "Meet our new stormwater specialist",  # 'special' inside a word is not a Special Meeting
        "Skateboard park ribbon cutting",
        "Family board game night at the library",
        "Mayor's holiday message",
        "",
        None,
    ],
)
def test_titles_that_name_no_meeting_stay_other(title):
    assert mt.meeting_type_from_title(title) == "Other"


def test_the_scraper_uses_the_same_classifier():
    from pathlib import Path

    src = (Path(mt.__file__).parent / "scrape_youtube_channels.py").read_text(encoding="utf-8")
    assert "meeting_type_from_title(title)" in src
    assert "return 'Other'" not in src  # the old substring ladder is gone


def test_only_untyped_rows_with_a_telling_title_are_retyped():
    rows = [
        ("v1", "Other", "Tuscaloosa Finance Committee Meeting"),
        ("v2", "", "Pre-Council Briefing"),
        ("v3", None, "Historic Preservation Commission"),
        ("v4", "YouTube Video", "Capital Projects Work Session"),
        ("v5", "UNKNOWN", "Public Hearing"),
        ("v6", "Other", "Water park opens"),          # title names nothing: left alone
        ("v7", "City Council", "Finance Committee"),  # already typed: never changed
        ("v8", "Planning Commission", None),
    ]
    assert mt.plan_retype(rows) == [
        ("v1", "Other", "Committee"),
        ("v2", "", "Briefing"),
        ("v3", "", "Commission"),
        ("v4", "YouTube Video", "Work Session"),
        ("v5", "UNKNOWN", "Public Hearing"),
    ]


def test_local_warehouse_url_never_uses_production(monkeypatch):
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://prod.example/db")
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    assert mt.local_warehouse_url() == "postgresql://postgres:pw@localhost:5433/open_navigator"
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://dev.example/db")
    assert mt.local_warehouse_url() == "postgresql://dev.example/db"


def test_cli_is_a_dry_run_unless_apply(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setattr(mt, "run", lambda **kw: seen.append(kw) or {})
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    assert mt.main([]) == 0 and seen[-1]["apply"] is False and seen[-1]["states"] is None
    assert mt.main(["--states", "al, ga", "--apply"]) == 0
    assert seen[-1]["apply"] is True and seen[-1]["states"] == ("AL", "GA")
    assert "localhost:5433" in seen[-1]["database_url"]
