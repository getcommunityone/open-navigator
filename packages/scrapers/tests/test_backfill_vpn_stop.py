"""backfill_jurisdiction_transcripts stops with exit 5 when the VPN drops (#488).

The database, YouTube and the VPN check are all replaced; no network.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

import pytest

from scrapers.youtube import backfill_jurisdiction_transcripts as bf
from scrapers.youtube import bronze_transcript_tracking as btt
from scrapers.youtube import transcript_api_client as tac
from scrapers.youtube import vpn_refresh
from scrapers.youtube.vpn_guard import VpnRequiredError

ROWS = [
    {
        "video_id": vid,
        "title": f"Council {vid}",
        "bronze_has_transcript": False,
        "event_id": None,
    }
    for vid in ("vidA", "vidB", "vidC")
]


class _FakeLoader:
    instances: list["_FakeLoader"] = []
    fetch: Callable[[str], Any] = staticmethod(
        lambda vid: {"raw_text": "hello", "segments": []}
    )

    def __init__(self, **kwargs: Any) -> None:
        self.conn = object()
        self.fetched: list[str] = []
        self.closed = False
        _FakeLoader.instances.append(self)

    def fetch_transcript(self, video_id: str) -> Any:
        self.fetched.append(video_id)
        return type(self).fetch(video_id)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path):
    import llm.gemini.policy_exclusions as pe
    import llm.gemini.transcript_cache_paths as tcp

    _FakeLoader.instances = []
    _FakeLoader.fetch = staticmethod(lambda vid: {"raw_text": "hello", "segments": []})
    saved: list[str] = []
    errors: list[tuple[str, str]] = []
    tombstones: list[str] = []

    monkeypatch.setattr(bf, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(tcp, "resolve_canonical_jurisdiction_id", lambda j: j)
    monkeypatch.setattr(bf, "_effective_state_code", lambda *a, **k: "AL")
    monkeypatch.setattr(
        bf, "fetch_pending_videos", lambda *a, **k: [dict(r) for r in ROWS]
    )
    monkeypatch.setattr(bf, "local_transcript_exists", lambda *a, **k: False)
    monkeypatch.setattr(bf, "sync_existing_local_transcript", lambda *a, **k: None)
    monkeypatch.setattr(pe, "filter_rows_not_excluded", lambda rows, *a, **k: rows)
    monkeypatch.setattr(bf, "resolve_cookies_path", lambda *a, **k: None)
    monkeypatch.setattr(tac, "log_caption_fetch_setup", lambda *a, **k: None)
    monkeypatch.setattr(bf, "YouTubeEventsLoader", _FakeLoader)
    monkeypatch.setattr(
        btt, "ensure_bronze_youtube_transcript_columns", lambda conn: None
    )
    monkeypatch.setattr(
        btt,
        "record_transcript_download_success",
        lambda conn, vid, path: saved.append(vid),
    )
    monkeypatch.setattr(
        btt,
        "record_transcript_download_error",
        lambda conn, vid, err: errors.append((vid, err)),
    )
    monkeypatch.setattr(vpn_refresh, "refresh_enabled", lambda: False)
    monkeypatch.setattr(bf, "upsert_bronze_transcript", lambda conn, vid, yt: None)
    monkeypatch.setattr(
        bf,
        "write_transcript_tombstone",
        lambda *a, **k: tombstones.append(k.get("video_id")),
    )
    monkeypatch.setattr(bf.time, "sleep", lambda s: None)

    def run_main() -> int:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "backfill",
                "--jurisdiction-id",
                "municipality_test",
                "--database-url",
                "postgresql://unused",
                "--skip-probe",
                "--no-clear-tombstones",
                "--no-dedupe-duplicates",
                "--no-local-cache",
                "--delay",
                "0",
                "--local-cache-dir",
                str(tmp_path),
            ],
        )
        with pytest.raises(SystemExit) as exc:
            bf.main()
        return exc.value.code

    return {
        "run": run_main,
        "saved": saved,
        "errors": errors,
        "tombstones": tombstones,
        "monkeypatch": monkeypatch,
    }


def _vpn_sequence(monkeypatch: pytest.MonkeyPatch, outcomes: list[bool]) -> list[int]:
    """require_vpn passes/fails per call, in order (then keeps the last outcome)."""
    calls: list[int] = []

    def fake_require_vpn(**kwargs: Any) -> None:
        i = len(calls)
        calls.append(i)
        ok = outcomes[min(i, len(outcomes) - 1)]
        if not ok:
            raise VpnRequiredError("Surfshark is off: connect it, then re-run")

    monkeypatch.setattr(bf, "require_vpn", fake_require_vpn)
    return calls


def test_vpn_off_at_start_exits_5_before_any_fetch(harness):
    _vpn_sequence(harness["monkeypatch"], [False])
    assert harness["run"]() == 5
    assert _FakeLoader.instances == []  # never got as far as building the loader


def test_mid_run_drop_saves_progress_and_exits_5(harness):
    # start check, vidA check pass; vidB check fails.
    calls = _vpn_sequence(harness["monkeypatch"], [True, True, False])
    assert harness["run"]() == 5
    loader = _FakeLoader.instances[0]
    assert loader.fetched == ["vidA"]  # vidB and vidC never reached YouTube
    assert harness["saved"] == ["vidA"]  # vidA's progress was saved normally
    assert harness["errors"] == [] and harness["tombstones"] == []
    assert loader.closed
    assert len(calls) == 3


def test_vpn_error_from_the_fetch_is_not_a_failure_or_tombstone(harness):
    _vpn_sequence(harness["monkeypatch"], [True])

    def fetch(vid: str) -> Any:
        if vid == "vidB":
            raise VpnRequiredError("dropped during the request")
        return {"raw_text": "hello", "segments": []}

    _FakeLoader.fetch = staticmethod(fetch)
    assert harness["run"]() == 5
    assert _FakeLoader.instances[0].fetched == ["vidA", "vidB"]
    assert harness["errors"] == [] and harness["tombstones"] == []


def test_vpn_up_whole_run_exits_0(harness):
    calls = _vpn_sequence(harness["monkeypatch"], [True])
    assert harness["run"]() == 0
    assert _FakeLoader.instances[0].fetched == ["vidA", "vidB", "vidC"]
    assert len(calls) == 4  # start + one re-check before each YouTube fetch
