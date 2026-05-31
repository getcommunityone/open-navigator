{% macro address_match_key(street, city, state_code, zip) -%}
    /*
        Deterministic blocking key for an address: md5 of the normalized
        street + city + 2-letter state + zip5, pipe-delimited. Two rows with the
        same key are the same mailable address and can be equi-joined cheaply
        before any fuzzy comparison runs.

        Returns NULL when the street normalizes to nothing — a streetless row
        (blank street_line1, PO-box-only, etc.) must NOT block as an exact address,
        or every streetless parcel in a city/zip collapses into one key (observed:
        11k+ Selma AL rows on a single hash). City/state/zip-only proximity is
        Splink's job, not the deterministic key's.

        Usage:
            {% raw %}{{ address_match_key('address', 'city', 'state_code', 'zip') }}{% endraw %}
    */
CASE
    WHEN {{ normalize_address(street) }} IS NULL THEN NULL
    ELSE MD5(
        {{ normalize_address(street) }} || '|' ||
        COALESCE(LOWER(TRIM(UNACCENT({{ city }}))), '') || '|' ||
        COALESCE(LOWER(TRIM({{ state_code }})), '') || '|' ||
        COALESCE({{ zip5(zip) }}, '')
    )
END
{%- endmacro %}
