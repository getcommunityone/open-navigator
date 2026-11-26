"""#1089: the business and business_mention marts are served on Neon (they are small: only named businesses)."""

from __future__ import annotations

from hosting.neon.sync_public_to_neon import CIVIC_SERVING, NON_SERVING

BUSINESS_SERVING = {"business", "business_mention"}


def test_business_marts_are_mirrored() -> None:
    assert BUSINESS_SERVING <= CIVIC_SERVING


def test_business_marts_are_not_on_the_non_serving_list() -> None:
    assert not BUSINESS_SERVING & NON_SERVING


def test_the_organization_master_stays_unserved() -> None:
    # business replaces the search over the 4.2M-row master, so the master itself still doesn't ship
    assert "mdm_organization" in NON_SERVING
    assert "mdm_organization" not in CIVIC_SERVING
