{#
    normalize_place_key(expr)

    Produces an UPPER-cased place-name key for joining heterogeneous
    place/jurisdiction labels onto the bare-city grain used by
    jurisdiction_state_aggregate (whose city_keys are UPPER(city)).

    It strips a single trailing governmental-unit suffix so that labels like
    "Tuscaloosa County", "Tuscaloosa Government" and "Bulloch County" collapse
    onto the bare city/place key ("TUSCALOOSA", "BULLOCH") that the nonprofit /
    person / event sources expose. Casing is preserved as UPPER so the result
    is directly comparable to UPPER(city) elsewhere in the mart.

    Note: deliberately conservative — only a trailing unit word is removed, and
    only one of them, so multi-word place names (e.g. "New York") are untouched.
#}
{% macro normalize_place_key(expr) -%}
TRIM(REGEXP_REPLACE(
    UPPER(TRIM({{ expr }})),
    '\s+(COUNTY|GOVERNMENT|CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP|PARISH|MUNICIPALITY|CCD)$',
    '',
    'g'
))
{%- endmacro %}
