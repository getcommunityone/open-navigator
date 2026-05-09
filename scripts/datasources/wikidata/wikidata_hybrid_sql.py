"""Thin WDQS SELECT bodies for hybrid mode — id→item only (+ optional identifiers on the binding)."""

# Same VALUES as ``municipality_mapping_sparql`` / legacy P131+ city crawl.
MUNICIPALITY_PLACE_TYPE_VALUES = (
    "wd:Q515 wd:Q3957 wd:Q15284 wd:Q486972 wd:Q493522 wd:Q1115575 "
    "wd:Q1549591 wd:Q15222645 wd:Q2989398 wd:Q1426695"
)


def municipality_mapping_sparql(filt: str, limit_rows: int) -> str:
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      VALUES ?placeType {{
        {MUNICIPALITY_PLACE_TYPE_VALUES}
      }}
      ?item wdt:P31 ?placeType .
      ?item wdt:P17 wd:Q30 .
      OPTIONAL {{ ?item wdt:P774 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      {filt}
    }}
    LIMIT {limit_rows}
    """


def municipality_bulk_by_state_sparql(state_q_code: str, limit_rows: int = 8000) -> str:
    """
    One WDQS query per state: place types with transitive P131+ to the state (same geographic
    scope as the legacy wide city query). Match bronze P774/P590 literals in-process.
    """
    sc = (state_q_code or "").strip()
    if not sc.startswith("Q"):
        sc = f"Q{sc}"
    lim = max(200, min(12000, int(limit_rows)))
    pt = MUNICIPALITY_PLACE_TYPE_VALUES
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      VALUES ?placeType {{ {pt} }}
      ?item wdt:P31 ?placeType .
      ?item wdt:P17 wd:Q30 .
      ?item wdt:P131+ wd:{sc} .
      OPTIONAL {{ ?item wdt:P774 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
    }}
    LIMIT {lim}
    """


def county_mapping_sparql(county_type_values: str, in_list_sql: str, limit_rows: int) -> str:
    return f"""
    SELECT DISTINCT ?item ?fips ?fipsAlt ?gnis WHERE {{
      VALUES ?countyType {{ {county_type_values} }}
      ?item wdt:P31 ?countyType .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P3006 ?fipsAlt . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      FILTER(
        (BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN ({in_list_sql}))
        || (BOUND(?fipsAlt) && REPLACE(STR(?fipsAlt), "-", "") IN ({in_list_sql}))
      )
    }}
    LIMIT {limit_rows}
    """


def county_bulk_by_state_sparql(county_type_values: str, state_q_code: str, limit_rows: int = 600) -> str:
    """
    One WDQS query per state: all county-like entities (P31) in the US (P17) with P131 = state.
    Match bronze GEOIDs in-process — no giant FILTER IN, no per-county w/api.php search.
    """
    sc = (state_q_code or "").strip()
    if not sc.startswith("Q"):
        sc = f"Q{sc}"
    lim = max(50, min(2000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?fipsAlt ?gnis WHERE {{
      VALUES ?countyType {{ {county_type_values} }}
      ?item wdt:P31 ?countyType .
      ?item wdt:P17 wd:Q30 .
      ?item wdt:P131 wd:{sc} .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P3006 ?fipsAlt . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
    }}
    LIMIT {lim}
    """


def school_mapping_sparql(in_list_sql: str, limit_rows: int) -> str:
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis ?nces WHERE {{
      ?item wdt:P31 wd:Q1455778 .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      OPTIONAL {{ ?item wdt:P6545 ?nces . }}
      FILTER(
        (BOUND(?nces) && REPLACE(STR(?nces), "-", "") IN ({in_list_sql}))
        || (BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN ({in_list_sql}))
      )
    }}
    LIMIT {limit_rows}
    """


def school_bulk_by_state_sparql(state_q_code: str, limit_rows: int = 2500) -> str:
    """
    One WDQS query per state: school districts (Q1455778) under the state via P131+
    (same scope as ``_query_schools_in_state_wide``). Match NCES / FIPS literals in-process.
    """
    sc = (state_q_code or "").strip()
    if not sc.startswith("Q"):
        sc = f"Q{sc}"
    lim = max(100, min(5000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis ?nces WHERE {{
      ?item wdt:P31 wd:Q1455778 .
      ?item wdt:P17 wd:Q30 .
      ?item wdt:P131+ wd:{sc} .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      OPTIONAL {{ ?item wdt:P6545 ?nces . }}
    }}
    LIMIT {lim}
    """
