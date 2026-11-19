"""#593: scrub invented Tuscaloosa demo jurisdiction labels."""

from llm.gemini.meeting_jurisdiction import (
    is_invented_tuscaloosa_jurisdiction,
    scrub_meeting_jurisdiction,
)


def test_bare_id_is_always_invented():
    assert is_invented_tuscaloosa_jurisdiction(
        "tuscaloosa_0177256", place_name="City of Tuscaloosa", jurisdiction_id="tuscaloosa_0177256"
    )
    assert is_invented_tuscaloosa_jurisdiction(
        "tuscaloosa_0177256", place_name="Dublin", jurisdiction_id="municipality_123"
    )


def test_demo_label_on_foreign_place_is_invented():
    assert is_invented_tuscaloosa_jurisdiction(
        "City of Tuscaloosa, Alabama",
        place_name="Dublin",
        jurisdiction_id="municipality_0132475",
    )


def test_real_tuscaloosa_label_on_tuscaloosa_place_is_kept():
    assert not is_invented_tuscaloosa_jurisdiction(
        "City of Tuscaloosa, Alabama",
        place_name="City of Tuscaloosa",
        jurisdiction_id="municipality_0177256",
    )


def test_scrub_clears_invented_and_keeps_honest():
    bad = scrub_meeting_jurisdiction(
        {"meeting": {"jurisdiction": "City of Tuscaloosa, Alabama", "body_name": "Council"}},
        place_name="Medford",
        jurisdiction_id="municipality_ma",
    )
    assert bad["meeting"]["jurisdiction"] is None
    assert bad["meeting"]["body_name"] == "Council"

    good = scrub_meeting_jurisdiction(
        {"meeting": {"jurisdiction": "City of Tuscaloosa, Alabama"}},
        place_name="City of Tuscaloosa",
        jurisdiction_id="municipality_0177256",
    )
    assert good["meeting"]["jurisdiction"] == "City of Tuscaloosa, Alabama"
