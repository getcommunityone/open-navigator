from llm.gemini.transcript_cache_paths import (
    extract_meeting_date_from_filename,
    extract_meeting_date_from_title,
    meeting_media_basename,
    resolve_meeting_event_date,
    strip_meeting_date_from_title,
)


def test_extract_slash_date_from_council_title():
    title = "City of Northport - Council Meeting 9/23/2024"
    assert extract_meeting_date_from_title(title) == "2024-09-23"


def test_resolve_uses_iso_prefix_from_audio_path():
    title = "Behind Beloit Pilot"
    audio = "WI/Some_Channel/2026-02-25_260123_Behind_Beloit_Pilot.opus"
    assert extract_meeting_date_from_filename(audio) == "2026-02-25"
    assert (
        resolve_meeting_event_date(
            title,
            event_date="2026-05-26",
            published_at="2026-05-26",
            audio_file_path=audio,
        )
        == "2026-02-25"
    )
    assert (
        meeting_media_basename(title, event_date="2026-05-26", audio_file_path=audio)
        == "2026-02-25_Behind_Beloit_Pilot"
    )


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


def test_meeting_media_basename_ordinal_month_at_end():
    title = "Commissioners Meeting May 4th, 2026"
    assert extract_meeting_date_from_title(title) == "2026-05-04"
    assert meeting_media_basename(title) == "2026-05-04_Commissioners_Meeting"
    assert strip_meeting_date_from_title(title, resolved_date="2026-05-04") == "Commissioners Meeting"


def test_extract_ordinal_from_underscore_basename():
    title = "Redevelopment_Commission_Meeting_May_14th,_2026"
    assert extract_meeting_date_from_title(title) == "2026-05-14"
    assert (
        meeting_media_basename(title, event_date="2026-05-15")
        == "2026-05-14_Redevelopment_Commission_Meeting"
    )


def test_extract_space_separated_mdy_two_digit_year():
    title = "Board of Public Works Meeting 1 8 26"
    assert extract_meeting_date_from_title(title) == "2026-01-08"
    assert extract_meeting_date_from_title("Board_of_Public_Works_Meeting_1_8_26") == "2026-01-08"
    assert (
        meeting_media_basename(title, event_date="2026-02-17")
        == "2026-01-08_Board_of_Public_Works_Meeting"
    )


def test_extract_space_separated_mdy_four_digit_year():
    assert extract_meeting_date_from_title("City Council Regular Meeting 4 28 2026 Video") == "2026-04-28"
    assert extract_meeting_date_from_title("East Chicago Common Council Meeting 02 25 2026") == "2026-02-25"
    assert extract_meeting_date_from_title("US Senator David Perdue Brookhaven Chamber 4 11 17") == "2017-04-11"


def test_meeting_media_basename_slash_becomes_hyphen_without_duplicate_date():
    title = "City of Northport - Council Meeting 1/11/2024"
    base = meeting_media_basename(title, event_date="2025-04-04")
    assert base == "2024-01-11_City_of_Northport_-_Council_Meeting"


def test_extract_two_digit_year_hyphen_from_board_title():
    title = "Board of Commissioners Meeting 1-23-24"
    assert extract_meeting_date_from_title(title) == "2024-01-23"


def test_meeting_media_basename_two_digit_year_in_title():
    title = "Board of Commissioners Meeting 1-23-24"
    base = meeting_media_basename(title, event_date=None)
    assert base == "2024-01-23_Board_of_Commissioners_Meeting"


def test_extract_slash_two_digit_year():
    assert extract_meeting_date_from_title("Council 3/5/25") == "2025-03-05"


def test_extract_compact_yyyymmdd_prefix():
    title = "20171107 Andalusia City Council Meeting November 7 2017"
    assert extract_meeting_date_from_title(title) == "2017-11-07"
    base = meeting_media_basename(title)
    assert base.startswith("2017-11-07_")
    assert "20171107" not in base


def test_strip_compact_legacy_suffix():
    from llm.gemini.transcript_cache_paths import strip_meeting_date_from_title

    assert (
        strip_meeting_date_from_title(
            "City of Northport - Council Meeting 1112024",
            resolved_date="2024-01-11",
        )
        == "City of Northport - Council Meeting"
    )
