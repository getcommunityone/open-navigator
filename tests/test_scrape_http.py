"""Tests for VPN/proxy bypass retry helpers."""

from scripts.discovery.scrape_http import (
    is_scrape_transport_or_vpn_failure,
    scrape_vpn_bypass_retry_enabled,
)


def test_scrape_vpn_bypass_default_on():
    assert scrape_vpn_bypass_retry_enabled() is True


def test_transport_failure_status_codes():
    assert is_scrape_transport_or_vpn_failure(status_code=403) is True
    assert is_scrape_transport_or_vpn_failure(status_code=200) is False


def test_transport_failure_timeout():
    import httpx

    assert is_scrape_transport_or_vpn_failure(exc=httpx.ConnectTimeout("t")) is True
