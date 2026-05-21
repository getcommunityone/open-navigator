from scripts.gemini.transcript_cache_paths import (
    extract_meeting_date_from_title,
    meeting_media_basename,
    resolve_meeting_event_date,
)


def test_extract_slash_date_from_council_title():
    title = "City of Northport - Council Meeting 9/23/2024"
    assert extract_meeting_date_from_title(title) == "2024-09-23"


def test_resolve_prefers_title_over_upload_date():
    title = "City of Northport - Council Meeting 9/23/2024"
    assert (
        resolve_meeting_event_date(title, event_date="2025-04-04", published_at="2025-04-04")
        == "2024-09-23"
    )


def test_meeting_media_basename_uses_title_date():
    title = "City of Northport - Council Meeting 9/23/2024"
    base = meeting_media_basename(title, event_date="2025-04-04")
    assert base == "2024-09-23_City_of_Northport_-_Council_Meeting"


def test_meeting_media_basename_slash_becomes_hyphen_without_duplicate_date():
    title = "City of Northport - Council Meeting 1/11/2024"
    base = meeting_media_basename(title, event_date="2025-04-04")
    assert base == "2024-01-11_City_of_Northport_-_Council_Meeting"


def test_strip_compact_legacy_suffix():
    from scripts.gemini.transcript_cache_paths import strip_meeting_date_from_title

    assert (
        strip_meeting_date_from_title(
            "City of Northport - Council Meeting 1112024",
            resolved_date="2024-01-11",
        )
        == "City of Northport - Council Meeting"
    )
