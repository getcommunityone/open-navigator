"""Unit tests for the BLS CPI ingestion pipeline.

Offline-only — no network, no DB. The fetch/load paths are exercised through
the deterministic helpers (cache pathing, response melting, row schema,
window chunking, current-year refetch rule) so CI can run these without
``BLS_API_KEY`` and without a Postgres instance.
"""
from __future__ import annotations

import datetime as dt
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.bls.cpi import (  # noqa: E402
    BlsCpiRow,
    cache_path_for,
    chunk_windows,
    fetch_window,
    melt_bls_response,
    _is_invalid_key_response,
    _window_must_refetch,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_cache_path_is_deterministic_and_namespaced(tmp_path: Path) -> None:
    p1 = cache_path_for("CUUR0000SA0", 2000, 2019, cache_dir=tmp_path)
    p2 = cache_path_for("CUUR0000SA0", 2000, 2019, cache_dir=tmp_path)
    p3 = cache_path_for("CUUR0000SA0", 2020, 2024, cache_dir=tmp_path)
    p4 = cache_path_for("CUUR0100SA0", 2000, 2019, cache_dir=tmp_path)
    assert p1 == p2
    assert p1 != p3  # different window
    assert p1 != p4  # different series
    assert p1.suffix == ".json"
    assert "CUUR0000SA0" in p1.name and "2000-2019" in p1.name


def test_chunk_windows_caps_at_twenty_years() -> None:
    # 21-year span → two windows: 20yr + 1yr
    windows = chunk_windows(2000, 2020)
    assert windows == [(2000, 2019), (2020, 2020)]
    # Exact 20-year fit → single window
    assert chunk_windows(2000, 2019) == [(2000, 2019)]
    # Single year
    assert chunk_windows(2024, 2024) == [(2024, 2024)]


def test_window_must_refetch_current_year_is_stale() -> None:
    # Current calendar year is always treated as stale (annual avg lags).
    today = dt.date(2026, 5, 28)
    assert _window_must_refetch(2026, today=today) is True
    assert _window_must_refetch(2027, today=today) is True
    # Historical fully-published years are stable.
    assert _window_must_refetch(2025, today=today) is False
    assert _window_must_refetch(2000, today=today) is False


_SAMPLE_BLS_RESPONSE: dict = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {
        "series": [
            {
                "seriesID": "CUUR0000SA0",
                "data": [
                    {
                        "year": "2024",
                        "period": "M13",
                        "periodName": "Annual",
                        "value": "313.689",
                        "footnotes": [{}],
                    },
                    {
                        "year": "2024",
                        "period": "M12",
                        "periodName": "December",
                        "value": "315.605",
                        "footnotes": [{"text": "Revised."}],
                    },
                    {
                        "year": "2024",
                        "period": "M11",
                        "periodName": "November",
                        "value": "315.493",
                        "footnotes": [],
                    },
                    # Defensive: an unparsable value should be skipped, not raise.
                    {
                        "year": "2024",
                        "period": "M10",
                        "periodName": "October",
                        "value": "n/a",
                        "footnotes": [],
                    },
                ],
            }
        ]
    },
}


def test_melt_response_yields_expected_rows() -> None:
    rows = list(melt_bls_response(_SAMPLE_BLS_RESPONSE, source_version="t"))
    # 4 input data points, 1 unparsable → 3 valid rows
    assert len(rows) == 3
    annual = next(r for r in rows if r["period"] == "M13")
    assert annual["series_id"] == "CUUR0000SA0"
    assert annual["year"] == 2024
    assert annual["value"] == pytest.approx(313.689)
    assert annual["period_name"] == "Annual"
    assert annual["natural_key"] == "CUUR0000SA0:2024:M13"
    assert annual["source"] == "bls_cpi"
    # Footnotes are concatenated and empty entries elided.
    dec = next(r for r in rows if r["period"] == "M12")
    assert dec["footnotes"] == "Revised."
    nov = next(r for r in rows if r["period"] == "M11")
    assert nov["footnotes"] is None


def test_melt_response_empty_payload_is_safe() -> None:
    assert list(melt_bls_response({}, source_version="t")) == []
    assert list(melt_bls_response({"Results": {}}, source_version="t")) == []
    assert (
        list(melt_bls_response({"Results": {"series": []}}, source_version="t")) == []
    )


def test_bls_cpi_row_schema_accepts_valid() -> None:
    row = BlsCpiRow(
        source="bls_cpi",
        source_version="t",
        natural_key="CUUR0000SA0:2024:M13",
        series_id="CUUR0000SA0",
        year=2024,
        period="M13",
        period_name="Annual",
        value=313.689,
        footnotes=None,
    )
    assert row.series_id == "CUUR0000SA0"
    assert row.value == pytest.approx(313.689)


def test_bls_cpi_row_schema_rejects_oversized_period() -> None:
    with pytest.raises(Exception):
        BlsCpiRow(
            source="bls_cpi",
            source_version="t",
            natural_key="x",
            series_id="CUUR0000SA0",
            year=2024,
            period="M13_TOO_LONG_FIELD",  # > 8 chars
            period_name="Annual",
            value=1.0,
        )


def test_is_invalid_key_response_discriminates() -> None:
    # The exact rejection BLS returns for a bad key → retry keyless.
    assert _is_invalid_key_response(
        "REQUEST_NOT_PROCESSED",
        ["The key:abc provided by the User is invalid. Please provide a proper key"],
    )
    # A successful request is never an invalid-key case.
    assert not _is_invalid_key_response("REQUEST_SUCCEEDED", [])
    # Other not-processed failures (e.g. rate limit) aren't fixed by dropping
    # the key, so they must not trigger the keyless retry.
    assert not _is_invalid_key_response(
        "REQUEST_NOT_PROCESSED",
        ["Request could not be serviced, as the daily threshold has been reached."],
    )


def test_fetch_window_retries_unregistered_on_invalid_key(tmp_path: Path) -> None:
    """A rejected registered key falls back to an unregistered (keyless)
    request rather than crashing the run, since BLS serves the same series
    without a key (at a lower rate limit)."""

    class _FakeResponse:
        def __init__(self, body: dict) -> None:
            self._body = body

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self._body

    class _FakeClient:
        """Rejects any request carrying a registrationkey; succeeds without."""

        def __init__(self) -> None:
            self.payloads: list[dict] = []

        async def post(self, url: str, *, json: dict, timeout: int) -> _FakeResponse:
            self.payloads.append(json)
            if "registrationkey" in json:
                return _FakeResponse(
                    {
                        "status": "REQUEST_NOT_PROCESSED",
                        "message": ["The key:bad provided by the User is invalid."],
                    }
                )
            return _FakeResponse({"status": "REQUEST_SUCCEEDED", "Results": {"series": []}})

    import asyncio

    client = _FakeClient()
    path = asyncio.run(
        fetch_window(
            client,  # type: ignore[arg-type]
            "CUUR0000SA0",
            2020,
            2020,
            "bad-key",
            cache_dir=tmp_path,
        )
    )
    # Two POSTs: first with the key (rejected), then keyless (succeeds).
    assert len(client.payloads) == 2
    assert "registrationkey" in client.payloads[0]
    assert "registrationkey" not in client.payloads[1]
    # The successful (keyless) body is what gets cached.
    assert path.exists()
    cached = json.loads(path.read_text())
    assert cached["status"] == "REQUEST_SUCCEEDED"


def test_no_fetch_with_missing_cache_raises(tmp_path: Path) -> None:
    """``--no-fetch`` must fail loudly when a window is not cached, rather
    than silently producing a partial result set that would deflate dollar
    values inconsistently downstream."""
    from ingestion.bls.cpi import BlsCpiPipeline

    pipe = BlsCpiPipeline(
        series_id="CUUR0000SA0",
        start_year=2024,
        end_year=2024,
        cache_dir=tmp_path,
        allow_fetch=False,
    )

    async def _drain() -> None:
        async for _ in pipe.extract(_ctx()):
            pass

    import asyncio

    with pytest.raises(FileNotFoundError):
        asyncio.run(_drain())


def test_extract_reads_cached_window(tmp_path: Path) -> None:
    """When the cache file exists for the requested window AND the window
    is not the current calendar year, ``--no-fetch`` should replay it."""
    from ingestion.bls.cpi import BlsCpiPipeline

    # Pick a year safely in the historical past so the current-year refetch
    # rule doesn't kick in even with --no-fetch off; here allow_fetch=False
    # so the rule is irrelevant anyway, but choose 2020 for clarity.
    series = "CUUR0000SA0"
    p = cache_path_for(series, 2020, 2020, cache_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_SAMPLE_BLS_RESPONSE))

    pipe = BlsCpiPipeline(
        series_id=series,
        start_year=2020,
        end_year=2020,
        cache_dir=tmp_path,
        allow_fetch=False,
    )

    async def _collect() -> list[dict]:
        out: list[dict] = []
        async for r in pipe.extract(_ctx()):
            out.append(r)
        return out

    import asyncio

    rows = asyncio.run(_collect())
    # 3 valid rows from the sample (one unparsable was dropped).
    assert len(rows) == 3
    assert {r["period"] for r in rows} == {"M13", "M12", "M11"}
