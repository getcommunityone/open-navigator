"""load_awards: --months restricts windows; --max-window-rows is passed to the client (#1478)."""

from __future__ import annotations

from datetime import date

from ingestion.usaspending import load_awards


class _FakeClient:
    calls: list[tuple[date, date, int]] = []

    def iter_awards(self, start, end, recipient_type, aln, max_rows):
        _FakeClient.calls.append((start, end, max_rows))
        return iter(())


def test_months_and_max_window_rows(monkeypatch):
    _FakeClient.calls = []
    monkeypatch.setattr(load_awards, "UsaSpendingClient", _FakeClient)
    rc = load_awards.main(
        ["--dry-run", "--fy-start", "2022", "--fy-end", "2023",
         "--months", "2022-02,2023-09", "--max-window-rows", "1000"]
    )
    assert rc == 0
    assert _FakeClient.calls == [
        (date(2022, 2, 1), date(2022, 2, 28), 1000),
        (date(2023, 9, 1), date(2023, 9, 30), 1000),
    ]
