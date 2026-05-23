"""Tests for built-in jurisdiction contact seed URL priority."""

from scripts.discovery.jurisdiction_contact_seed_urls import merged_contact_seed_urls


def test_bulloch_commissioners_seed_is_prepended() -> None:
    seeds = merged_contact_seed_urls(
        "county_13031",
        ["https://example.org/contacts", "https://bullochcounty.net/commissioners/"],
    )
    assert seeds[0] == "https://bullochcounty.net/commissioners/"
    assert seeds.count("https://bullochcounty.net/commissioners/") == 1
    assert "https://example.org/contacts" in seeds
