"""Google Data Commons client for jurisdiction enrichment.

Uses the Google Data Commons Knowledge Graph to enrich jurisdiction data with:
- Demographics (population, age, gender, race/ethnicity)
- Economic indicators (income, employment, poverty)
- Education levels
- Health insurance coverage
- Housing characteristics

Ported from scripts/datasources/google_data_commons/google_data_commons.py to the
ingestion workspace package. The original relied on the legacy ``datacommons`` /
``datacommons_pandas`` SDKs, whose REST endpoints (``api.datacommons.org/stat/*``)
were deprecated and now return HTTP 410. Following the same modernization the
data_gov port made, the transport is reimplemented against the supported
Data Commons **v2 REST API** (``/v2/observation``) via ``httpx`` — no SDK
dependency. The statistical-variable catalog (DEMOGRAPHIC_VARS … HOUSING_VARS),
the FIPS→DCID convention, and the public method surface are preserved.

API base: https://api.datacommons.org/v2
Docs:     https://docs.datacommons.org/api/rest/v2/
Get a free API key: https://apikeys.datacommons.org/

Citation:
    Google LLC. Data Commons. https://datacommons.org/
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

API_BASE = "https://api.datacommons.org/v2"
DATA_SOURCE = "Google Data Commons"


class DataCommonsClient:
    """Client for enriching jurisdiction data with Google Data Commons variables.

    Replaces manual U.S. Census API calls with the Data Commons observation API.
    A free API key is required (https://apikeys.datacommons.org/); pass it to the
    constructor or set the ``DATA_COMMONS_API_KEY`` environment variable.
    """

    # Standard statistical variables for jurisdictions
    DEMOGRAPHIC_VARS = [
        "Count_Person",                                          # Total population
        "Count_Person_Male",                                     # Male population
        "Count_Person_Female",                                   # Female population
        "Median_Age_Person",                                     # Median age
        "Count_Person_WhiteAlone",                              # White population
        "Count_Person_BlackOrAfricanAmericanAlone",             # Black population
        "Count_Person_HispanicOrLatino",                        # Hispanic/Latino
        "Count_Person_AsianAlone",                              # Asian population
    ]

    ECONOMIC_VARS = [
        "Median_Income_Household",                              # Median household income
        "UnemploymentRate_Person",                              # Unemployment rate
        "Count_Person_BelowPovertyLevelInThePast12Months",     # Poverty count
        "Median_Earnings_Person",                               # Median earnings
    ]

    EDUCATION_VARS = [
        "Count_Person_EducationalAttainmentBachelorsDegreeOrHigher",  # College graduates
        "Count_Person_EducationalAttainmentHighSchoolGraduateOrHigher",  # HS graduates
    ]

    HEALTH_VARS = [
        "Count_Person_WithHealthInsurance",                     # Insured population
        "Count_Person_NoHealthInsurance",                       # Uninsured population
    ]

    HOUSING_VARS = [
        "Median_Price_SoldHome",                                # Median home price
        "Count_HousingUnit",                                    # Total housing units
        "Count_Household",                                      # Total households
    ]

    ALL_VARS = (
        DEMOGRAPHIC_VARS
        + ECONOMIC_VARS
        + EDUCATION_VARS
        + HEALTH_VARS
        + HOUSING_VARS
    )

    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        """Initialize the Data Commons client.

        Args:
            api_key: Data Commons API key. Falls back to the
                ``DATA_COMMONS_API_KEY`` environment variable.
            timeout: HTTP timeout in seconds.
        """
        self.api_key = api_key or os.getenv("DATA_COMMONS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No Data Commons API key. Pass api_key= or set "
                "DATA_COMMONS_API_KEY. Get a free key at "
                "https://apikeys.datacommons.org/"
            )
        self.timeout = timeout

    def get_place_dcid(self, fips_code: str, place_type: str = "County") -> str:
        """Convert a FIPS code to a Data Commons ID (DCID).

        Args:
            fips_code: 5-digit FIPS code (state+county) or 7-digit (state+place).
            place_type: "County" or "City" (informational; the DCID form is the
                same ``geoId/<fips>`` for both).

        Returns:
            DCID like "geoId/01073" for Jefferson County, AL.

        Examples:
            >>> client = DataCommonsClient(api_key="...")
            >>> client.get_place_dcid("01073", "County")
            'geoId/01073'
            >>> client.get_place_dcid("0107000", "City")  # Birmingham, AL
            'geoId/0107000'
        """
        return f"geoId/{fips_code}"

    def fetch_observations(
        self,
        dcids: list[str],
        variables: list[str],
        date: str = "LATEST",
    ) -> dict[str, dict[str, Any]]:
        """Fetch observations for many places/variables from the v2 API.

        Args:
            dcids: Place DCIDs (e.g. ``["geoId/01073"]``).
            variables: Statistical variable DCIDs.
            date: ``"LATEST"`` (default), ``""`` for all dates, or a specific year.

        Returns:
            Nested dict ``{dcid: {variable: {"value": v, "date": d}}}``. Missing
            observations are simply absent.
        """
        # POST (not GET) so bulk requests with hundreds of entities don't blow
        # past URL-length limits. The v2 API accepts the same shape as a body.
        body: dict[str, Any] = {
            "select": ["entity", "variable", "value"],
            "entity": {"dcids": list(dcids)},
            "variable": {"dcids": list(variables)},
            "date": date,
        }
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        url = f"{API_BASE}/observation"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.post(url, json=body, headers=headers)

        if resp.status_code >= 400:
            body = resp.text[:400].replace("\n", " ")
            logger.error("HTTP {} from {} — {}", resp.status_code, url, body)
            resp.raise_for_status()

        payload = resp.json()
        out: dict[str, dict[str, Any]] = {d: {} for d in dcids}
        by_variable = payload.get("byVariable", {}) or {}
        for var, var_block in by_variable.items():
            by_entity = (var_block or {}).get("byEntity", {}) or {}
            for dcid, ent_block in by_entity.items():
                facets = (ent_block or {}).get("orderedFacets", []) or []
                # The first ordered facet is the preferred source; first
                # observation within it is the requested (e.g. LATEST) point.
                obs = None
                for facet in facets:
                    observations = facet.get("observations") or []
                    if observations:
                        obs = observations[0]
                        break
                if obs is not None:
                    out.setdefault(dcid, {})[var] = {
                        "value": obs.get("value"),
                        "date": obs.get("date"),
                    }
        return out

    def enrich_jurisdiction(
        self,
        fips_code: str,
        variables: list[str] | None = None,
    ) -> dict[str, Any]:
        """Enrich a single jurisdiction with Data Commons variables.

        Args:
            fips_code: 5-digit (county) or 7-digit (city) FIPS code.
            variables: Statistical variables (default: ``ALL_VARS``).

        Returns:
            Flat dict ``{variable: value, ...}`` plus ``fips_code``, ``dcid``,
            ``data_source`` and ``retrieval_date`` metadata. On error, a dict
            with ``fips_code`` and ``error``.
        """
        if variables is None:
            variables = self.ALL_VARS

        dcid = self.get_place_dcid(fips_code)
        try:
            observations = self.fetch_observations([dcid], variables)
            place_obs = observations.get(dcid, {})
            result: dict[str, Any] = {
                "fips_code": fips_code,
                "dcid": dcid,
                "data_source": DATA_SOURCE,
                "retrieval_date": datetime.now(timezone.utc).isoformat(),
            }
            for var in variables:
                obs = place_obs.get(var)
                result[var] = obs.get("value") if obs else None
            return result
        except Exception as e:  # noqa: BLE001 — preserve original best-effort contract
            logger.error("Error enriching {}: {}", fips_code, e)
            return {"fips_code": fips_code, "error": str(e)}

    def enrich_jurisdictions_bulk(
        self,
        fips_codes: list[str],
        variables: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Enrich many jurisdictions in one request.

        Note: the original SDK-based version returned a pandas ``DataFrame``;
        this port returns a list of flat dicts (one per jurisdiction) so the
        bronze loader can consume it directly. Build a DataFrame with
        ``pandas.DataFrame(rows)`` if needed.

        Args:
            fips_codes: List of FIPS codes.
            variables: Statistical variables (default: ``ALL_VARS``).

        Returns:
            One flat dict per input FIPS code, in input order.
        """
        if variables is None:
            variables = self.ALL_VARS

        dcids = [self.get_place_dcid(f) for f in fips_codes]
        try:
            observations = self.fetch_observations(dcids, variables)
        except Exception as e:  # noqa: BLE001
            logger.error("Error enriching bulk jurisdictions: {}", e)
            return [{"fips_code": f, "error": str(e)} for f in fips_codes]

        retrieval_date = datetime.now(timezone.utc).isoformat()
        rows: list[dict[str, Any]] = []
        for fips, dcid in zip(fips_codes, dcids):
            place_obs = observations.get(dcid, {})
            row: dict[str, Any] = {
                "fips_code": fips,
                "dcid": dcid,
                "data_source": DATA_SOURCE,
                "retrieval_date": retrieval_date,
            }
            for var in variables:
                obs = place_obs.get(var)
                row[var] = obs.get("value") if obs else None
            rows.append(row)
        return rows
