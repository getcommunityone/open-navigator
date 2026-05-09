"""Thin WDQS SELECT bodies for hybrid mode — id→item only (+ optional identifiers on the binding)."""

# Legacy: explicit populated-place ``instance of`` values (unused for thin P774/P590 mapping).
MUNICIPALITY_PLACE_TYPE_VALUES = (
    "wd:Q515 wd:Q3957 wd:Q15284 wd:Q486972 wd:Q493522 wd:Q1115575 "
    "wd:Q1549591 wd:Q15222645 wd:Q2989398 wd:Q1426695"
)


def municipality_mapping_sparql(fips_in: str, gnis_in: str, limit_rows: int) -> str:
    """
    **Property-led** municipality id lookup: require ``wdt:P774`` / ``wdt:P590`` (indexed), no ``P17`` scan,
    no OPTIONAL+BOUND. Non-empty ``fips_in`` / ``gnis_in`` are comma-separated **quoted** literals; pass ``""``
    to omit a branch. Multiple branches use ``UNION``.

    P774 values on WDQS mix ``SS-CCCPP`` hyphenated and compact 7-digit strings; the FIPS branch compares
    ``REPLACE(STR(?fips), "-", "")`` so ``fips_in`` literals should be **digits-only** (hyphens stripped).
    """
    branches = []
    if fips_in.strip():
        branches.append(
            '{{ ?item wdt:P774 ?fips . FILTER(REPLACE(STR(?fips), "-", "") IN ({fips_in})) }}'.format(
                fips_in=fips_in
            )
        )
    if gnis_in.strip():
        branches.append(f"{{ ?item wdt:P590 ?gnis . FILTER(?gnis IN ({gnis_in})) }}")
    if not branches:
        raise ValueError("municipality_mapping_sparql: both fips_in and gnis_in are empty")
    union = "\n      UNION\n      ".join(branches)
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      {union}
    }}
    LIMIT {limit_rows}
    """


def municipality_bulk_by_state_sparql(state_q_code: str, limit_rows: int = 8000) -> str:
    """
    One WDQS query per state: entities transitively under the state item via ``P131+``.
    No ``wdt:P17`` (avoids intersecting the full US set first). Match bronze P774/P590 in-process.
    OPTIONals remain so rows without identifiers still appear for secondary matching where applicable.
    """
    sc = (state_q_code or "").strip()
    if not sc.startswith("Q"):
        sc = f"Q{sc}"
    lim = max(200, min(12000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      ?item wdt:P131+ wd:{sc} .
      OPTIONAL {{ ?item wdt:P774 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
    }}
    LIMIT {lim}
    """


def county_mapping_sparql(county_type_values: str, in_list_sql: str, limit_rows: int) -> str:
    """
    Require ``P882`` or ``P3006`` with ``FILTER(?… IN (...))`` — separate UNION branches (indexed leads).
    Literals must be pre-cleaned (no dashes).
    """
    return f"""
    SELECT DISTINCT ?item ?fips ?fipsAlt ?gnis WHERE {{
      {{
        VALUES ?countyType {{ {county_type_values} }}
        ?item wdt:P31 ?countyType .
        ?item wdt:P882 ?fips .
        FILTER(?fips IN ({in_list_sql}))
      }}
      UNION
      {{
        VALUES ?countyType {{ {county_type_values} }}
        ?item wdt:P31 ?countyType .
        ?item wdt:P3006 ?fipsAlt .
        FILTER(?fipsAlt IN ({in_list_sql}))
      }}
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
    """School district: UNION ``P6545`` vs ``P882`` branches with required triples (no OPTIONAL+BOUND)."""
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis ?nces WHERE {{
      {{
        ?item wdt:P31 wd:Q1455778 .
        ?item wdt:P6545 ?nces .
        FILTER(?nces IN ({in_list_sql}))
      }}
      UNION
      {{
        ?item wdt:P31 wd:Q1455778 .
        ?item wdt:P882 ?fips .
        FILTER(?fips IN ({in_list_sql}))
      }}
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
