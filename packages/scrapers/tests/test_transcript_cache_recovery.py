"""#458: transcripts reach bronze without an event_id, the cache lives under the repo
root, and misplaced transcripts can be recovered (temp dirs + mocked DB only)."""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core_lib.paths import find_repo_root, repo_root

SCRAPERS_SRC = Path(__file__).resolve().parents[1] / "src" / "scrapers"
REPO = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- repo root


def test_repo_root_contains_agents_md() -> None:
    root = repo_root(__file__)
    assert (root / "AGENTS.md").is_file()
    assert root == REPO


def test_find_repo_root_walks_up_from_nested_file(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("x")
    nested = tmp_path / "packages" / "pkg" / "src" / "pkg" / "sub"
    nested.mkdir(parents=True)
    mod = nested / "mod.py"
    mod.write_text("")
    assert find_repo_root(mod) == tmp_path


def test_repo_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_NAVIGATOR_REPO_ROOT", str(tmp_path))
    assert repo_root(__file__) == tmp_path.resolve()


def test_default_local_cache_is_under_repo_root() -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    root = bf._REPO_ROOT
    assert (root / "AGENTS.md").is_file()
    assert bf.DEFAULT_LOCAL_CACHE == root / "data" / "cache" / "gemini_transcript_policy"
    assert "packages" not in bf.DEFAULT_LOCAL_CACHE.relative_to(root).parts


@pytest.mark.parametrize(
    "module",
    [
        "scrapers.youtube.backfill_jurisdiction_transcripts",
        "scrapers.youtube.policy_transcript_cache",
        "scrapers.youtube.bronze_transcript_tracking",
        "scrapers.youtube.youtube_loader_logging",
        "scrapers.youtube.normalize_youtube_jurisdiction_ids",
    ],
)
def test_youtube_module_repo_root_has_agents_md(module: str) -> None:
    mod = importlib.import_module(module)
    root = getattr(mod, "_REPO_ROOT", None) or getattr(mod, "_REPO")
    assert (Path(root) / "AGENTS.md").is_file()


def test_no_hardcoded_parents3_repo_root_in_scrapers() -> None:
    """parents[3] from scrapers/<sub>/<mod>.py is packages/scrapers, never the repo root."""
    pattern = re.compile(r"Path\(__file__\)\.resolve\(\)\.parents\[3\]")
    offenders = [
        str(p.relative_to(SCRAPERS_SRC))
        for p in SCRAPERS_SRC.rglob("*.py")
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# --------------------------------------------------------------------------- bronze upsert


def _fake_conn(bronze_ids: set[str] | None = None) -> MagicMock:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [(v,) for v in sorted(bronze_ids or set())]
    conn.cursor.return_value = cur
    return conn


def test_upsert_bronze_transcript_needs_no_event_id() -> None:
    from scrapers.youtube.backfill_jurisdiction_transcripts import upsert_bronze_transcript

    conn = _fake_conn()
    yt = {
        "raw_text": "hello council",
        "segments": [{"text": "hello council", "start": 0.0, "duration": 1.0}],
        "language": "en",
        "is_auto_generated": True,
        "transcript_source": "youtube_transcript_api",
    }
    upsert_bronze_transcript(conn, "q4fbeH64mxk", yt)

    cur = conn.cursor.return_value
    sql, params = cur.execute.call_args.args
    assert "INSERT INTO bronze.bronze_event_youtube_transcript" in sql
    assert "ON CONFLICT (video_id) DO UPDATE" in sql
    assert "event_id" not in params
    assert params["video_id"] == "q4fbeH64mxk"
    assert json.loads(params["segments"]) == yt["segments"]
    assert params["transcript_quality"] == "medium"
    conn.commit.assert_called_once()
    cur.close.assert_called_once()


def test_backfill_run_does_not_gate_bronze_upsert_on_event_id() -> None:
    """The run loop calls upsert_bronze_transcript outside any ``if ... event_id`` branch."""
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    tree = ast.parse(Path(bf.__file__).read_text(encoding="utf-8"))
    run_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")

    found: list[bool] = []

    def visit(node: ast.AST, gated: bool) -> None:
        if isinstance(node, ast.If):
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            child_gated = gated or "event_id" in names
            for child in node.body:
                visit(child, child_gated)
            for child in node.orelse:
                visit(child, gated)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "upsert_bronze_transcript"
        ):
            found.append(gated)
        for child in ast.iter_child_nodes(node):
            visit(child, gated)

    visit(run_fn, False)
    assert found == [False]


# --------------------------------------------------------------------------- recovery CLI


def _write_transcript(
    root: Path, rel: str, video_id: str, *, raw_text: str = "words", segments: bool = True
) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    seg = [{"text": raw_text, "start": 0.0, "duration": 1.0}]
    payload: dict[str, Any] = {
        "video_id": video_id,
        "title": "Board Meeting",
        "jurisdiction_id": "j_1",
        "state_code": "MS",
        "youtube": {
            "video_id": video_id,
            "raw_text": raw_text,
            "language": "en",
            "is_auto_generated": True,
            "transcript_source": "youtube_transcript_api",
        },
        "transcript_source": "youtube_transcript_api",
        "caption_raw_data": seg,
    }
    if segments:
        payload["youtube"]["segments"] = seg
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def caches(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "packages" / "scrapers" / "data" / "cache" / "gemini_transcript_policy"
    dst = tmp_path / "data" / "cache" / "gemini_transcript_policy"
    base = "MS/municipality/j_1/_unknown/01_transcripts"
    _write_transcript(src, f"{base}/a.json", "vid_new")
    _write_transcript(src, f"{base}/b.json", "vid_in_bronze")
    _write_transcript(src, f"{base}/c.json", "vid_exists_dest", segments=False)
    _write_transcript(src, f"{base}/d.json", "vid_empty", raw_text="")
    _write_transcript(src, "MS/municipality/j_1/UCabc/01_transcripts/e.json", "vid_new")
    (src / "MS/municipality/j_1/_unknown/02_analysis").mkdir(parents=True)
    (src / "MS/municipality/j_1/_unknown/02_analysis/x.json").write_text("{}")
    existing = dst / f"{base}/c.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("ORIGINAL")
    return src, dst


def test_recover_dry_run_writes_nothing(caches: tuple[Path, Path]) -> None:
    from scrapers.youtube.recover_misplaced_transcripts import recover

    src, dst = caches
    conn = _fake_conn({"vid_in_bronze"})
    upsert = MagicMock()
    stats = recover(source_root=src, dest_root=dst, conn=conn, apply=False, upsert=upsert)

    assert stats.files == 5
    assert stats.bronze_loaded == 2  # vid_new + vid_exists_dest
    assert stats.bronze_duplicate == 1  # vid_new seen twice
    assert stats.bronze_present == 1
    assert stats.no_transcript == 1
    assert stats.copied == 4
    assert stats.copy_skipped_exists == 1
    upsert.assert_not_called()
    conn.commit.assert_not_called()
    assert not (dst / "MS/municipality/j_1/_unknown/01_transcripts/a.json").exists()
    assert (dst / "MS/municipality/j_1/_unknown/01_transcripts/c.json").read_text() == "ORIGINAL"


def test_recover_apply_loads_and_copies_without_overwriting(caches: tuple[Path, Path]) -> None:
    from scrapers.youtube.recover_misplaced_transcripts import recover

    src, dst = caches
    conn = _fake_conn({"vid_in_bronze"})
    upsert = MagicMock()
    stats = recover(source_root=src, dest_root=dst, conn=conn, apply=True, upsert=upsert)

    loaded = {c.args[1]: c.args[2] for c in upsert.call_args_list}
    assert set(loaded) == {"vid_new", "vid_exists_dest"}
    # Segments fall back to top-level caption_raw_data when the youtube block lacks them.
    assert loaded["vid_exists_dest"]["segments"][0]["text"] == "words"
    assert stats.copied == 4
    base = dst / "MS/municipality/j_1/_unknown/01_transcripts"
    assert json.loads((base / "a.json").read_text())["video_id"] == "vid_new"
    assert (base / "c.json").read_text() == "ORIGINAL"
    assert (dst / "MS/municipality/j_1/UCabc/01_transcripts/e.json").is_file()
    assert not (dst / "MS/municipality/j_1/_unknown/02_analysis").exists()
    # Copy, not move: every source file is still there.
    assert len(list(src.rglob("01_transcripts/*.json"))) == 5


def test_recover_limit(caches: tuple[Path, Path]) -> None:
    from scrapers.youtube.recover_misplaced_transcripts import recover

    src, dst = caches
    stats = recover(
        source_root=src, dest_root=dst, conn=_fake_conn(), apply=False, limit=2, upsert=MagicMock()
    )
    assert stats.files == 2


def test_recover_uses_backfill_upsert_by_default(
    caches: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf
    from scrapers.youtube.recover_misplaced_transcripts import recover

    calls: list[str] = []
    monkeypatch.setattr(bf, "upsert_bronze_transcript", lambda conn, vid, yt: calls.append(vid))
    src, dst = caches
    recover(source_root=src, dest_root=dst, conn=_fake_conn({"vid_in_bronze"}), apply=True)
    assert sorted(calls) == ["vid_exists_dest", "vid_new"]


def test_cli_defaults_resolve_under_repo_root() -> None:
    from scrapers.youtube import recover_misplaced_transcripts as rm

    assert rm.DEFAULT_DEST_ROOT == REPO / "data" / "cache" / "gemini_transcript_policy"
    assert rm.DEFAULT_SOURCE_ROOT == (
        REPO / "packages" / "scrapers" / "data" / "cache" / "gemini_transcript_policy"
    )


# --------------------------------------------------------------------------- no re-download guard


_ROW = {
    "video_id": "q4fbeH64mxk",
    "title": "CMSD Regular Board Meeting 1/13/25",
    "event_date": "2025-01-13",
    "jurisdiction_id": "columbus_municipal_school_district_2801200",
    "jurisdiction_type": "municipality",
    "state_code": "MS",
    "channel_id": "",
    "video_url": "https://www.youtube.com/watch?v=q4fbeH64mxk",
    "bronze_has_transcript": None,
}
_YT = {
    "video_id": "q4fbeH64mxk",
    "raw_text": "call to order",
    "segments": [{"text": "call to order", "start": 0.0, "duration": 2.0}],
    "language": "en",
    "is_auto_generated": True,
    "transcript_source": "youtube_transcript_api",
}


def _cache_row(cache: Path) -> Path:
    from scrapers.youtube.backfill_jurisdiction_transcripts import write_local_transcript

    return write_local_transcript(
        cache, row=dict(_ROW), yt=dict(_YT), cache_dir=cache, state_code="MS"
    )


def _sync(cache: Path, legacy: Path, conn: Any, **kw: Any):
    from scrapers.youtube.backfill_jurisdiction_transcripts import (
        sync_existing_local_transcript,
    )

    return sync_existing_local_transcript(
        conn,
        cache_dir=cache,
        jurisdiction_id=_ROW["jurisdiction_id"],
        row=dict(_ROW),
        state_code="MS",
        legacy_cache_dirs=(legacy,),
        **kw,
    )


def test_guard_loads_file_in_cache_into_bronze(tmp_path: Path) -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    cache, legacy = tmp_path / "cache", tmp_path / "legacy"
    path = _cache_row(cache)
    conn = _fake_conn()
    upsert = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bf, "upsert_bronze_transcript", upsert)
        result = _sync(cache, legacy, conn)
    assert result is not None and result.path == path and result.loaded_to_bronze
    assert result.copied_to is None
    (c,) = upsert.call_args_list
    assert c.args[1] == "q4fbeH64mxk" and c.args[2]["raw_text"] == "call to order"


def test_guard_finds_legacy_package_cache_and_copies_it(tmp_path: Path) -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    cache, legacy = tmp_path / "cache", tmp_path / "legacy"
    legacy_path = _cache_row(legacy)
    upsert = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bf, "upsert_bronze_transcript", upsert)
        result = _sync(cache, legacy, _fake_conn())
    assert result is not None and result.path == legacy_path
    assert result.copied_to == cache / legacy_path.relative_to(legacy)
    assert result.copied_to.is_file() and legacy_path.is_file()  # copied, not moved
    upsert.assert_called_once()


def test_guard_without_bronze_write_still_skips_youtube(tmp_path: Path) -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    cache, legacy = tmp_path / "cache", tmp_path / "legacy"
    _cache_row(cache)
    upsert = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bf, "upsert_bronze_transcript", upsert)
        result = _sync(cache, legacy, _fake_conn(), write_bronze=False)
    assert result is not None and not result.loaded_to_bronze
    upsert.assert_not_called()


def test_guard_returns_none_when_nothing_cached(tmp_path: Path) -> None:
    result = _sync(tmp_path / "cache", tmp_path / "legacy", _fake_conn())
    assert result is None


def test_guard_ignores_file_for_another_video(tmp_path: Path) -> None:
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    cache, legacy = tmp_path / "cache", tmp_path / "legacy"
    path = _cache_row(cache)
    data = json.loads(path.read_text())
    data["video_id"] = data["youtube"]["video_id"] = "otherVideo1"
    path.write_text(json.dumps(data))
    upsert = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bf, "upsert_bronze_transcript", upsert)
        assert _sync(cache, legacy, _fake_conn()) is None
    upsert.assert_not_called()


def test_run_loop_tries_local_cache_before_youtube() -> None:
    """In run(), sync_existing_local_transcript is called before loader.fetch_transcript."""
    from scrapers.youtube import backfill_jurisdiction_transcripts as bf

    src = Path(bf.__file__).read_text(encoding="utf-8")
    run_src = src[src.index("def run(args"):]
    guard = run_src.index("sync_existing_local_transcript(")
    fetch = run_src.index("loader.fetch_transcript(video_id)")
    assert guard < fetch
