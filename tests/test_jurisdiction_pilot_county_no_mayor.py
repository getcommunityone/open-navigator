"""Counties must not probe or scrape mayor office pages."""

from scripts.datasources.jurisdiction_pilot.mayor_url_discovery import (
    candidate_urls,
    discover_seed_urls,
)
from scripts.datasources.jurisdiction_pilot.scrape_priority_states import (
    Jurisdiction,
    _resolve_seed_urls,
)


def test_county_candidate_urls_skip_mayor_paths():
    home = "https://www.bartowcountyga.gov/"
    mayor_paths = candidate_urls(home, kind="mayor")
    muni_council_paths = candidate_urls(home, kind="council")
    county_council_paths = candidate_urls(home, kind="council", jurisdiction_type="county")
    assert any("/mayor" in p for p in mayor_paths)
    assert not any("/mayor" in p for p in muni_council_paths)
    assert any("citycouncil" in p or "city-council" in p for p in muni_council_paths)
    assert not any("citycouncil" in p or "city-council" in p for p in county_council_paths)
    assert any("commission" in p for p in county_council_paths)


def test_discover_seed_urls_county_returns_no_mayor(monkeypatch):
    probed: list[tuple[str, str]] = []

    def fake_probe(urls, *, session=None):
        for u in urls:
            if "/mayor" in u:
                probed.append(("mayor", u))
            else:
                probed.append(("council", u))
        return list(urls)[:1] if urls else []

    monkeypatch.setattr(
        "scripts.datasources.jurisdiction_pilot.mayor_url_discovery.probe_urls",
        fake_probe,
    )
    out = discover_seed_urls(
        "https://www.bartowcountyga.gov/",
        jurisdiction_type="county",
    )
    assert out["mayor"] == []
    assert not any(kind == "mayor" for kind, _ in probed)
    assert not any("citycouncil" in u or "city-council" in u for _, u in probed)


def test_resolve_seed_urls_county_excludes_mayor_seeds(monkeypatch):
    monkeypatch.setattr(
        "scripts.datasources.jurisdiction_pilot.scrape_priority_states.merged_contact_seed_urls",
        lambda _jid, _cli: (),
    )
    monkeypatch.setattr(
        "scripts.datasources.jurisdiction_pilot.scrape_priority_states.discover_seed_urls",
        lambda _url, jurisdiction_type=None: {
            "mayor": ["https://www.bartowcountyga.gov/mayor/"],
            "council": ["https://www.bartowcountyga.gov/commissioners/"],
        },
    )
    j = Jurisdiction(
        jurisdiction_id="bartow_13015",
        state_code="GA",
        jurisdiction_type="county",
        name="Bartow County",
        website_url="https://www.bartowcountyga.gov/",
    )
    seeds = _resolve_seed_urls(j)
    urls = [u for u, kind in seeds]
    kinds = {kind for _, kind in seeds}
    assert "https://www.bartowcountyga.gov/mayor/" not in urls
    assert "mayor" not in kinds
    assert any("commissioners" in u for u in urls)
