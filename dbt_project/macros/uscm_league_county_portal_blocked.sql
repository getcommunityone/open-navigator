{% macro uscm_league_county_portal_blocked(jurisdiction_name_expr, domain_name_expr) %}
(
    {{ website_domain_is_county_portal_host(domain_name_expr) }}
    AND NOT {{ municipality_name_allows_county_portal_url(jurisdiction_name_expr) }}
)
{% endmacro %}
