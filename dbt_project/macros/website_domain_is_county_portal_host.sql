{% macro website_domain_is_county_portal_host(domain_name_expr) %}
(
    COALESCE(LOWER(BTRIM({{ domain_name_expr }}::TEXT)), '') ~ '(^|\.)[a-z0-9-]*county\.(gov|us)$'
    OR COALESCE(LOWER(BTRIM({{ domain_name_expr }}::TEXT)), '') ~ '(^|\.)county\.[a-z0-9-]+\.(gov|us)$'
)
{% endmacro %}
