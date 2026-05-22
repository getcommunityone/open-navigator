"""public.jurisdiction — canonical jurisdiction row (replaces jurisdictions_details_search)."""

from __future__ import annotations

JURISDICTION_TABLE = "jurisdiction"

# Legacy jurisdictions_details_search column → jurisdiction column
DETAILS_TO_JURISDICTION = {
    "jurisdiction_name": "name",
    "jurisdiction_type": "type",
    "status": "discovery_status",
}
