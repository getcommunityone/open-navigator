{% macro municipality_name_allows_county_portal_url(jurisdiction_name_expr) %}
(
    LOWER(BTRIM({{ jurisdiction_name_expr }}::TEXT)) LIKE '%macon%bibb%'
    OR LOWER(BTRIM({{ jurisdiction_name_expr }}::TEXT)) LIKE '%city and county%'
    OR LOWER(BTRIM({{ jurisdiction_name_expr }}::TEXT)) LIKE '%city-county%'
    OR LOWER(BTRIM({{ jurisdiction_name_expr }}::TEXT)) LIKE '%city and borough%'
    OR LOWER(BTRIM({{ jurisdiction_name_expr }}::TEXT)) LIKE '% consolidated%'
)
{% endmacro %}
