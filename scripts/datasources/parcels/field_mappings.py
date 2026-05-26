"""
Canonical parcel attribute names and county-specific Esri field aliases.

Counties rarely share column names; map localized fields to a small standard
vocabulary before bronze load or cross-jurisdiction analytics.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

# canonical_name -> source aliases (first match wins, case-insensitive)
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "parcel_id": (
        "PARCEL_ID",
        "PARCELID",
        "PIN",
        "APN",
        "PROP_ID",
        "PROP_ID_NUM",
        "GEOPIN",
        "pclnum",
        "PCNUM_FMT",
        "PARCEL",
        "PARCEL_NUM",
        "ppin",
    ),
    "situs_address": (
        "SITUS_ADDRESS",
        "SITUS_ADDR",
        "PROP_ADR",
        "PROP_ADDR",
        "LOC_ADDR",
        "SITE_ADDR",
        "PHY_ADDR",
        "PROPERTY_ADDRESS",
        "pcliLocati",
        "ADDRESS",
        "SITEADDRESS",
    ),
    "owner_primary": (
        "OWNER_NAME",
        "OWNER1",
        "OWN_NAME",
        "PR_OWNER",
        "M_OWNER",
        "OWNER",
        "TAX_OWNER",
        "pcloNAME",
        "NAME1",
        "OWNERNAMES",
    ),
    "owner_secondary": (
        "OWNER2",
        "CO_OWNER",
        "SECONDARY_OWNER",
    ),
    "legal_description": (
        "LEGAL_DESC",
        "LEGAL_DESCRIPTION",
        "LEGAL",
        "LDESC",
    ),
    "appraised_improvement_value": (
        "IMPR_VAL",
        "IMP_VALUE",
        "BLDG_APPRAISAL",
        "IMPROVEMENT_VALUE",
        "BLDG_VAL",
    ),
    "appraised_land_value": (
        "LAND_VAL",
        "LAND_VALUE",
        "LAND_APPRAISAL",
    ),
    "appraised_total_value": (
        "TOTAL_VAL",
        "TOTAL_VALUE",
        "APPRAISED_VALUE",
        "APPR_VAL",
        "TOT_VAL",
        "ASSESSED_VALUE",
        "TOTAL_APPR",
        "appraised",
        "TOTALAPPR",
        "APPR_TOTAL",
    ),
    "tax_class": ("TaxClass", "TAX_CLASS", "CLASS", "PROP_CLASS"),
}


def build_rename_map(columns: Iterable[str]) -> dict[str, str]:
    """Map raw Esri column names to canonical names where an alias is recognized."""
    upper_to_orig = {str(c).upper(): str(c) for c in columns}
    renames: dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            orig = upper_to_orig.get(alias.upper())
            if orig is not None and orig not in renames:
                renames[orig] = canonical
                break
    return renames


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with recognized parcel fields renamed to canonical names."""
    renames = build_rename_map(df.columns)
    if not renames:
        return df.copy()
    return df.rename(columns=renames)
