{% macro normalize_name(name_column) %}
    /*
        Normalize person/organization names for fuzzy matching
        
        - Lowercase
        - Trim whitespace
        - Remove special characters (keep alphanumeric and spaces)
        - Collapse multiple spaces
        
        Usage:
            {% raw %}{{ normalize_name('full_name') }}{% endraw %}
    */
    TRIM(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(TRIM({{ name_column }})),
                '[^a-z0-9 ]', '', 'g'
            ),
            '\s+', ' ', 'g'
        )
    )
{% endmacro %}
