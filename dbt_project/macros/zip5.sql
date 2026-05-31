{% macro zip5(expr) -%}
    /*
        First 5 digits of a postal code, stripping ZIP+4, spaces, and any other
        non-digit noise. Empty result -> NULL.

        Usage: {% raw %}{{ zip5('contributor_zip') }}{% endraw %}
    */
NULLIF(
    LEFT(
        REGEXP_REPLACE(COALESCE({{ expr }}::text, ''), '[^0-9]', '', 'g'),
        5
    ),
    ''
)
{%- endmacro %}
