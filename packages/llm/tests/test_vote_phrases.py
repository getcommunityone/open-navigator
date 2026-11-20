# packages/llm/tests/test_vote_phrases.py
from llm.ner.spot import file_sha256, spot_segments


def test_spot_motion_and_result_with_seconds():
    segs = [
        {"text": "I move to approve Ordinance Number 12.", "start": 100.0},
        {"text": "Second.", "start": 105.0},
        {"text": "All in favor?", "start": 110.0},
        {"text": "Aye.", "start": 112.0},
        {"text": "Motion carries.", "start": 115.0},
    ]
    hits = spot_segments("vid1", segs)
    codes = [h.phrase_code for h in hits]
    assert "motion_made" in codes
    assert "seconded" in codes
    assert "vote_called" in codes
    assert "vote_cast" in codes
    assert "result" in codes
    assert "subject_cue" in codes
    assert any(h.start_seconds == 115.0 and h.phrase_code == "result" for h in hits)
    assert len(file_sha256(segs)) == 64


def test_create_sql_has_no_text_payload_and_singular_name():
    from llm.ner.store import CREATE_SQL, TABLE

    assert TABLE == "bronze.transcript_vote_phrase"
    assert "bronze.bronze_" not in TABLE
    assert "raw_text" not in CREATE_SQL.lower()
    assert "context" not in CREATE_SQL.lower()
    assert "file_sha256" in CREATE_SQL
    assert "git_commit_sha" in CREATE_SQL