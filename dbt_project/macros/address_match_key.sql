{% macro address_match_key(street, city, state_code, zip) -%}
    /*
        Deterministic blocking key for an address: md5 of the normalized
        street + city + 2-letter state + zip5, pipe-delimited. Two rows with the
        same key are the same mailable address and can be equi-joined cheaply
        before any fuzzy comparison runs.

        Usage:
            {% raw %}{{ address_match_key('address', 'city', 'state_code', 'zip') }}{% endraw %}
    */
MD5(
    COALESCE({{ normalize_address(street) }}, '') || '|' ||
    COALESCE(LOWER(TRIM(UNACCENT({{ city }}))), '') || '|' ||
    COALESCE(LOWER(TRIM({{ state_code }})), '') || '|' ||
    COALESCE({{ zip5(zip) }}, '')
)
{%- endmacro %}
