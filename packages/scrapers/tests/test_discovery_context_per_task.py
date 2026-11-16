"""Each concurrent discovery sees its own jurisdiction in ``_discovery_context``.

The jurisdiction discovery pipeline (a subclass of ComprehensiveDiscoveryPipeline)
sets ``self._discovery_context = jurisdiction`` and then awaits the parent's
``discover_jurisdiction``, whose ``_discover_website`` hook reads it back. As a plain
instance attribute it was shared by every concurrent task, so cities waiting on the
semaphore read another city's record or ``None``: the 6,407 city homepages were
saved, but no homepage was scanned for video links, meeting platforms, social media
or agenda portals.
"""

from __future__ import annotations

import asyncio
from typing import Any

from scrapers.discovery.comprehensive_discovery_pipeline import ComprehensiveDiscoveryPipeline


class _LegacyStyle(ComprehensiveDiscoveryPipeline):
    """Mirrors scripts/discovery/jurisdiction_discovery_pipeline.py's use of the context."""

    def __init__(self) -> None:
        self.semaphore = asyncio.Semaphore(2)
        self._discovery_context = None
        self.enable_wikidata = False
        self.seen: dict[str, Any] = {}

    async def _discover_website(self, name: str, state: str, jtype: str):
        await asyncio.sleep(0)  # let other tasks run, as real HTTP would
        j = self._discovery_context or {}
        self.seen[name] = j.get("name")
        url = j.get("homepage")
        return {"url": url} if url else None

    async def _discover_youtube(self, name, state, jtype, homepage_url):
        return [], []

    def _get_localview_channel(self, name, state):
        return None

    async def _discover_other_video(self, homepage_url):
        return [{"url": homepage_url}]

    async def _detect_meeting_platforms(self, name, state, homepage_url):
        return []

    async def _discover_social_media(self, homepage_url, name, state):
        return {"youtube": [f"{homepage_url}/yt"]}

    async def _find_agenda_portals(self, homepage_url, name):
        return []

    def _calculate_completeness(self, results):
        return 1.0

    async def discover_jurisdiction(self, jurisdiction):
        self._discovery_context = jurisdiction
        try:
            return await super().discover_jurisdiction(jurisdiction)
        finally:
            self._discovery_context = None


def test_concurrent_cities_each_see_their_own_homepage():
    cities = [
        {"name": f"City{i}", "state_code": "AL", "type": "city", "homepage": f"https://city{i}.gov"}
        for i in range(12)
    ]
    pipeline = _LegacyStyle()

    async def run():
        tasks = [asyncio.ensure_future(pipeline.discover_jurisdiction(c)) for c in cities]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run())

    assert pipeline.seen == {c["name"]: c["name"] for c in cities}
    for city, result in zip(cities, results):
        assert result["websites"] == [{"url": city["homepage"]}]
        assert result["social_media"] == {"youtube": [f"{city['homepage']}/yt"]}
        assert result["other_video"] == [{"url": city["homepage"]}]


def test_context_is_none_outside_a_discovery():
    pipeline = _LegacyStyle()
    assert pipeline._discovery_context is None
