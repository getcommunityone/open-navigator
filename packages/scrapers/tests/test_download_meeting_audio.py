"""Unit tests for scrapers.youtube.download_meeting_audio (#1255): no network, no database."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from scrapers.youtube import download_meeting_audio as dma


def _row(**kw):
    base = {
        "video_id": "Am_yPVh-Rik",
        "video_url": "https://www.youtube.com/watch?v=Am_yPVh-Rik",
        "title": "GFPS School Board Meeting (January 5th, 2026)",
        "meeting_date": date(2026, 1, 5),
        "event_date": None,
        "channel_id": "UCabc123",
        "channel_title": "Grand Forks Public Schools",
        "jurisdiction_name": "Grand Forks",
        "state_code": "ND",
        "duration_minutes": 60,
        "audio_file_path": None,
        "audio_downloaded_at": None,
    }
    base.update(kw)
    return base


def test_target_relpath_keeps_legacy_layout_and_adds_video_id():
    rel = dma.target_relpath(_row())
    assert rel.startswith(
        "nd/grand_forks_public_schools_ucabc123/2026-01-05_GFPS School Board"
    )
    assert rel.endswith(" [Am_yPVh-Rik].opus")


def test_block_errors_detected():
    assert dma.is_block_error(
        "ERROR: unable to download: HTTP Error 429: Too Many Requests"
    )
    assert dma.is_block_error("Sign in to confirm you're not a bot")
    assert dma.is_block_error("HTTP Error 403: Forbidden")
    assert not dma.is_block_error("This video is not available")


def test_estimate_fills_unknown_durations_with_average():
    est = dma.estimate(
        [
            _row(duration_minutes=60),
            _row(duration_minutes=120),
            _row(duration_minutes=None),
        ],
        64,
    )
    assert est["videos"] == 3
    assert est["hours"] == 4.5  # 60 + 120 + 90 minutes
    assert est["gb"] == pytest.approx(4.5 * 3600 * 8000 / 1e9, abs=0.1)


def test_scope_sql_excludes_non_meetings():
    sql = dma.scope_sql("data-centers")
    assert "data_center_meeting_mention" in sql and "data_center_meeting_lean" in sql
    assert "COALESCE(k.is_public_meeting, true)" in sql
    with pytest.raises(ValueError):
        dma.scope_sql("everything")


def _inv(target=(), local=()):
    inv = dma.Inventory()
    for rel in target:
        inv.add(dma.Location("target", "onedrive:CommunityOne/youtube_audio", rel, 10))
    for rel in local:
        inv.add(dma.Location("local", "/data/cache/youtube_audio", rel, 10))
    return inv


def test_video_id_in_any_filename_counts_as_held():
    inv = _inv(target=["misc/whatever_Am_yPVh-Rik.m4a"])
    p = dma.plan([_row()], inv)
    assert len(p.on_target) == 1 and not p.download


def test_legacy_name_and_tracked_path_match():
    legacy = (
        "nd/x_ucabc123/2026-01-05_GFPS School Board Meeting (January 5th, 2026).opus"
    )
    assert dma.plan([_row()], _inv(target=[legacy])).on_target
    tracked = _row(title=None, audio_file_path="al/mobile_uc/2026-05-05_x.opus")
    assert dma.plan(
        [tracked], _inv(local=["al/mobile_uc/2026-05-05_x.opus"])
    ).upload_local


def test_tracked_without_file_is_skipped_not_downloaded():
    p = dma.plan([_row(audio_file_path="gone/elsewhere.opus")], _inv())
    assert p.tracked_only and not p.download


def test_local_only_is_uploaded_not_downloaded(tmp_path: Path):
    src_root = tmp_path / "cache"
    (src_root / "nd" / "gfps_ucabc123").mkdir(parents=True)
    src = (
        src_root
        / "nd"
        / "gfps_ucabc123"
        / "2026-01-05_GFPS School Board Meeting (January 5th, 2026).opus"
    )
    src.write_bytes(b"x" * 100)
    out = tmp_path / "out"
    inv = dma.build_inventory(None, {}, [src_root])
    p = dma.plan([_row()], inv)
    called = []
    stats = dma.run(
        p,
        dma.LocalTarget(out),
        None,
        limit=None,
        kbps=64,
        cookies=None,
        sleep_seconds=0,
        max_blocks=3,
        temp_root=tmp_path,
        downloader=lambda *a: called.append(a),
        sleeper=lambda s: None,
    )
    assert stats.uploaded_existing == 1 and not called
    assert src.exists()  # the original is never deleted
    assert any(out.rglob("*Am_yPVh-Rik*.opus"))


def test_run_stops_after_repeated_blocks(tmp_path: Path):
    rows = [_row(video_id=f"vid{i:08d}") for i in range(5)]
    p = dma.plan(rows, dma.Inventory())

    def blocked(*_a):
        raise dma.Blocked("HTTP Error 429")

    pauses = []
    with pytest.raises(SystemExit) as exc:
        dma.run(
            p,
            dma.LocalTarget(tmp_path / "out"),
            None,
            limit=None,
            kbps=64,
            cookies=None,
            sleep_seconds=5,
            max_blocks=3,
            temp_root=tmp_path,
            downloader=blocked,
            sleeper=pauses.append,
        )
    assert exc.value.code == dma.EXIT_BLOCKED
    assert len(pauses) == 2 and pauses[1] > pauses[0]  # backs off, then stops
    assert not list(tmp_path.glob("audio_*"))  # temp dirs cleaned


def test_successful_download_moves_temp_file_and_cleans_up(tmp_path: Path):
    def fake(url, stem, kbps, cookies):
        out = stem.with_suffix(".opus")
        out.write_bytes(b"y" * 50)
        return out

    p = dma.plan([_row()], dma.Inventory())
    stats = dma.run(
        p,
        dma.LocalTarget(tmp_path / "out"),
        None,
        limit=1,
        kbps=64,
        cookies=None,
        sleep_seconds=0,
        max_blocks=3,
        temp_root=tmp_path,
        downloader=fake,
        sleeper=lambda s: None,
    )
    assert stats.done == 1 and stats.bytes_uploaded == 50
    assert not list(tmp_path.glob("audio_*"))


def test_legacy_name_in_another_channel_is_not_held():
    other = "va/some_town_ucother999/2026-01-05_GFPS School Board Meeting (January 5th, 2026).opus"
    p = dma.plan([_row()], _inv(local=[other]))
    assert p.download and not p.upload_local


def test_legacy_name_in_same_channel_folder_is_held():
    same = "nd/whatever_slug_ucabc123/2026-01-05_GFPS School Board Meeting (January 5th, 2026).opus"
    assert dma.plan([_row()], _inv(local=[same])).upload_local


class _ShortTarget(dma.LocalTarget):
    """Reports one byte fewer than written, to exercise the size check."""

    def put(self, local, relpath, *, move):
        return super().put(local, relpath, move=move) - 1


def test_size_mismatch_removes_our_copy(tmp_path: Path):
    def fake(url, stem, kbps, cookies):
        out = stem.with_suffix(".opus")
        out.write_bytes(b"z" * 40)
        return out

    out_dir = tmp_path / "out"
    stats = dma.run(
        dma.plan([_row()], dma.Inventory()),
        _ShortTarget(out_dir),
        None,
        limit=1,
        kbps=64,
        cookies=None,
        sleep_seconds=0,
        max_blocks=3,
        temp_root=tmp_path,
        downloader=fake,
        sleeper=lambda s: None,
    )
    assert stats.failed == 1 and stats.done == 0
    assert not list(out_dir.rglob("*.opus"))  # a bad copy never counts as held next run


class _FailingConn:
    def __init__(self):
        self.rolled_back = 0

    def cursor(self):
        raise RuntimeError("permission denied")

    def rollback(self):
        self.rolled_back += 1


def test_db_failure_after_upload_rolls_back_and_continues(tmp_path: Path):
    def fake(url, stem, kbps, cookies):
        out = stem.with_suffix(".opus")
        out.write_bytes(b"q" * 10)
        return out

    conn = _FailingConn()
    rows = [_row(video_id="aaaaaaaaaaa"), _row(video_id="bbbbbbbbbbb")]
    stats = dma.run(
        dma.plan(rows, dma.Inventory()),
        dma.LocalTarget(tmp_path / "out"),
        conn,
        limit=None,
        kbps=64,
        cookies=None,
        sleep_seconds=0,
        max_blocks=3,
        temp_root=tmp_path,
        downloader=fake,
        sleeper=lambda s: None,
    )
    assert stats.done == 2 and stats.not_recorded == 2 and conn.rolled_back == 2


def test_onedrive_listing_parses_rclone_output(monkeypatch):
    class P:
        returncode = 0
        stdout = "123\tva/x_uc1/2026-01-05_a [abcdefghijk].opus\n9\tnotes.txt\n"
        stderr = ""

    monkeypatch.setattr(dma.subprocess, "run", lambda *a, **k: P())
    files = dma.OneDriveTarget(
        remote="onedrive", root="CommunityOne/youtube_audio"
    ).listing()
    assert files == {"va/x_uc1/2026-01-05_a [abcdefghijk].opus": 123}


def test_onedrive_listing_missing_folder_is_empty(monkeypatch):
    class P:
        returncode = 3
        stdout = ""
        stderr = "error listing: directory not found"

    monkeypatch.setattr(dma.subprocess, "run", lambda *a, **k: P())
    assert dma.OneDriveTarget().listing() == {}
