"""Thin WDQS SELECT bodies for hybrid mode — id→item only (+ optional identifiers on the binding)."""


def municipality_mapping_sparql(filt: str, limit_rows: int) -> str:
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      VALUES ?placeType {{
        wd:Q515 wd:Q3957 wd:Q15284 wd:Q486972 wd:Q493522 wd:Q1115575
        wd:Q1549591 wd:Q15222645 wd:Q2989398 wd:Q1426695
      }}
      ?item wdt:P31 ?placeType .
      ?item wdt:P17 wd:Q30 .
      OPTIONAL {{ ?item wdt:P774 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      {filt}
    }}
    LIMIT {limit_rows}
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
