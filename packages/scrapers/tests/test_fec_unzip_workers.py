"""unzip_fec_data: `--workers 0` picks the worker count itself instead of crashing (#313).

The auto-detect branch called `cpu_count()`, which was never imported, so `--workers 0` raised NameError before any
file was unzipped. Every run here points `--base-dir` at a temp folder with an empty `bulk-downloads/`, so nothing
under data/cache/ is read or written.
"""

from __future__ import annotations

import sys

from scrapers.fec import unzip_fec_data as fec


def _workers_after_main(monkeypatch, tmp_path, *args: str) -> int:
    (tmp_path / "bulk-downloads").mkdir()
    seen: dict = {}

    class Spy(fec.FECBulkUnzipper):
        def __init__(self, *a, **k):
            seen.update(k)
            super().__init__(*a, **k)

    monkeypatch.setattr(fec, "FECBulkUnzipper", Spy)
    monkeypatch.setattr(sys, "argv", ["unzip_fec_data.py", "--base-dir", str(tmp_path), "--dry-run", *args])
    fec.main()
    return seen["workers"]


def test_workers_zero_picks_at_least_one_worker(monkeypatch, tmp_path):
    assert _workers_after_main(monkeypatch, tmp_path, "--workers", "0") >= 1


def test_an_explicit_worker_count_is_kept(monkeypatch, tmp_path):
    assert _workers_after_main(monkeypatch, tmp_path, "--workers", "3") == 3
