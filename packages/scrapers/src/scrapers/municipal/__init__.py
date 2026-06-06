"""Municipal-government scrapers (city council rosters, etc.)."""

from .council_roster import (
    CONFIGS,
    CURATED_ROSTERS,
    CouncilMember,
    MunicipalCouncilConfig,
    fetch_html,
    get_council,
    parse_council_html,
)

__all__ = [
    "CONFIGS",
    "CURATED_ROSTERS",
    "CouncilMember",
    "MunicipalCouncilConfig",
    "fetch_html",
    "get_council",
    "parse_council_html",
]
