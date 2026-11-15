"""An unsupported meeting platform is a gap, never "no meetings" (#252).

platform_detector mapped every platform it didn't know to `scrapers.generic.GenericScraper`, a module that doesn't
exist, and `get_scraper_class()` returned None. So a council on Granicus, PrimeGov or eScribe looked like a council
with no meetings. Both helpers now defer to `ingestion.meetings`: a platform without an adapter raises
`UnsupportedPlatformError`, and the discovery summary counts each jurisdiction's platforms that have no adapter.
"""

from __future__ import annotations

import csv

import pytest

from ingestion.meetings.registry import UnsupportedPlatformError
from scrapers.discovery import platform_detector as detector
from scrapers.discovery.comprehensive_discovery_pipeline import ComprehensiveDiscoveryPipeline


def test_a_platform_without_an_adapter_raises_instead_of_returning_none():
    with pytest.raises(UnsupportedPlatformError):
        detector.get_scraper_class("granicus", jurisdiction_name="Tuscaloosa")


def test_a_platform_with_an_adapter_returns_that_adapter():
    assert detector.get_scraper_class("legistar", jurisdiction_name="Tuscaloosa").platform_code == "legistar"


def test_capabilities_of_an_unknown_platform_raise_instead_of_a_generic_default():
    with pytest.raises(UnsupportedPlatformError):
        detector.get_platform_capabilities("primegov")
    assert detector.get_platform_capabilities("legistar")["has_api"] is True


def _result(name: str, platforms: list[dict]) -> dict:
    return {
        "jurisdiction": {"name": name, "state_code": "AL", "type": "city", "population": 1},
        "jurisdiction_id": f"{name.lower()}_0100001", "discovery_timestamp": "2026-11-14T00:00:00Z",
        "websites": [], "youtube_channels": [], "meeting_platforms": platforms, "social_media": {},
        "agenda_portals": [], "status": "ok", "completeness_score": 0.0,
    }


def test_the_discovery_summary_counts_platforms_without_an_adapter(tmp_path):
    pipeline = ComprehensiveDiscoveryPipeline.__new__(ComprehensiveDiscoveryPipeline)
    pipeline.output_dir, pipeline.gold_output_dir, pipeline.incremental = tmp_path, tmp_path, False
    pipeline._save_results([
        _result("Selma", [{"type": "legistar"}]),
        _result("Mobile", [{"type": "granicus"}, {"type": "legistar"}]),
        _result("Dothan", []),
    ], suffix="t")

    with open(next(tmp_path.glob("discovery_summary_t_*.csv")), encoding="utf-8") as f:
        rows = {r["name"]: r for r in csv.DictReader(f)}
    assert rows["Selma"]["meeting_platforms_without_adapter"] == "0"
    assert rows["Mobile"]["meeting_platforms_without_adapter"] == "1"
    assert rows["Dothan"]["meeting_platforms_without_adapter"] == "0"
