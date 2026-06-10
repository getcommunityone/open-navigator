"""Shared SQL for jurisdiction mapping quality (export JSON + API drill-down)."""

from __future__ import annotations

UNMAPPED_ROW_SELECT = """
    SELECT jurisdiction_id::text AS jurisdiction_id,
           name::text AS name,
           state_code::text AS state_code,
           jurisdiction_type::text AS jurisdiction_type,
           geoid::text AS geoid,
           municipality_place_kind::text AS municipality_place_kind,
           COALESCE(n_website_candidate_rows, 0)::bigint AS n_website_candidate_rows,
           COALESCE(has_naco_source, FALSE) AS has_naco_source,
           COALESCE(has_uscm_source, FALSE) AS has_uscm_source,
           COALESCE(has_nces_directory_source, FALSE) AS has_nces_directory_source,
           COALESCE(has_gsa_source, FALSE) AS has_gsa_source,
           COALESCE(has_league_source, FALSE) AS has_league_source,
           COALESCE(has_wikidata_source, FALSE) AS has_wikidata_source,
           COALESCE(has_override_source, FALSE) AS has_override_source,
           acs_population_tier::text AS acs_population_tier,
           acs_income_level::text AS acs_income_level
"""

MISSING_YOUTUBE_ROW_SELECT = """
    SELECT jurisdiction_id::text AS jurisdiction_id,
           name::text AS name,
           state_code::text AS state_code,
           jurisdiction_type::text AS jurisdiction_type,
           geoid::text AS geoid,
           municipality_place_kind::text AS municipality_place_kind,
           primary_website_url::text AS primary_website_url,
           COALESCE(has_primary_website, FALSE) AS has_primary_website,
           COALESCE(n_youtube_channel_rows, 0)::bigint AS n_youtube_channel_rows,
           acs_population_tier::text AS acs_population_tier,
           acs_income_level::text AS acs_income_level
"""

ENTITY_SLICE_WHERE: dict[str, str] = {
    "state": "jurisdiction_type = 'state'",
    "cities": (
        "jurisdiction_type = 'municipality' AND municipality_place_kind = 'incorporated_city'"
    ),
    "towns": (
        "jurisdiction_type = 'municipality' AND municipality_place_kind IN ("
        "'incorporated_other', 'unknown', 'census_designated_place'"
        ")"
    ),
    "counties": "jurisdiction_type = 'county'",
    "schools": "jurisdiction_type = 'school_district'",
}

VALID_ENTITIES = frozenset(ENTITY_SLICE_WHERE.keys())


def build_unmapped_where_psycopg(
    entity: str,
    *,
    state_code: str | None = None,
    acs_population_tier: str | None = None,
    acs_income_level: str | None = None,
) -> tuple[str, list[object]]:
    """WHERE fragment (no leading WHERE) and bound values for psycopg2 (%s)."""
    if entity not in ENTITY_SLICE_WHERE:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    parts = [
        "NOT COALESCE(has_primary_website, FALSE)",
        f"({ENTITY_SLICE_WHERE[entity]})",
    ]
    params: list[object] = []
    if state_code:
        parts.append("UPPER(TRIM(state_code::text)) = UPPER(TRIM(%s))")
        params.append(state_code.strip())
    if acs_population_tier:
        parts.append("acs_population_tier::text = %s")
        params.append(acs_population_tier.strip())
    if acs_income_level:
        parts.append("acs_income_level::text = %s")
        params.append(acs_income_level.strip())
    return " AND ".join(parts), params


def build_unmapped_where_asyncpg(
    entity: str,
    *,
    state_code: str | None = None,
    acs_population_tier: str | None = None,
    acs_income_level: str | None = None,
    param_start: int = 1,
) -> tuple[str, list[object], int]:
    """WHERE fragment and bound values for asyncpg ($n placeholders)."""
    if entity not in ENTITY_SLICE_WHERE:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    parts = [
        "NOT COALESCE(has_primary_website, FALSE)",
        f"({ENTITY_SLICE_WHERE[entity]})",
    ]
    params: list[object] = []
    n = param_start
    if state_code:
        parts.append(f"UPPER(TRIM(state_code::text)) = UPPER(TRIM(${n}::text))")
        params.append(state_code.strip())
        n += 1
    if acs_population_tier:
        parts.append(f"acs_population_tier::text = ${n}")
        params.append(acs_population_tier.strip())
        n += 1
    if acs_income_level:
        parts.append(f"acs_income_level::text = ${n}")
        params.append(acs_income_level.strip())
        n += 1
    return " AND ".join(parts), params, n


def build_missing_youtube_where_psycopg(
    entity: str,
    *,
    state_code: str | None = None,
    acs_population_tier: str | None = None,
    acs_income_level: str | None = None,
) -> tuple[str, list[object]]:
    """WHERE fragment for jurisdictions without a golden YouTube channel URL."""
    if entity not in ENTITY_SLICE_WHERE:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    parts = [
        "NOT COALESCE(has_youtube_channel, FALSE)",
        f"({ENTITY_SLICE_WHERE[entity]})",
    ]
    params: list[object] = []
    if state_code:
        parts.append("UPPER(TRIM(state_code::text)) = UPPER(TRIM(%s))")
        params.append(state_code.strip())
    if acs_population_tier:
        parts.append("acs_population_tier::text = %s")
        params.append(acs_population_tier.strip())
    if acs_income_level:
        parts.append("acs_income_level::text = %s")
        params.append(acs_income_level.strip())
    return " AND ".join(parts), params


def build_missing_youtube_where_asyncpg(
    entity: str,
    *,
    state_code: str | None = None,
    acs_population_tier: str | None = None,
    acs_income_level: str | None = None,
    param_start: int = 1,
) -> tuple[str, list[object], int]:
    """WHERE fragment for missing YouTube channel rows (asyncpg $n placeholders)."""
    if entity not in ENTITY_SLICE_WHERE:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    parts = [
        "NOT COALESCE(has_youtube_channel, FALSE)",
        f"({ENTITY_SLICE_WHERE[entity]})",
    ]
    params: list[object] = []
    n = param_start
    if state_code:
        parts.append(f"UPPER(TRIM(state_code::text)) = UPPER(TRIM(${n}::text))")
        params.append(state_code.strip())
        n += 1
    if acs_population_tier:
        parts.append(f"acs_population_tier::text = ${n}")
        params.append(acs_population_tier.strip())
        n += 1
    if acs_income_level:
        parts.append(f"acs_income_level::text = ${n}")
        params.append(acs_income_level.strip())
        n += 1
    return " AND ".join(parts), params, n
