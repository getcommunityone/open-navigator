{% macro normalize_person_name(expr) -%}
    /*
        Normalize a human name into a canonical match string.

          - unaccent + lowercase + trim
          - flip "Last, First"  ->  "first last"
          - drop leading honorifics/titles (mr, dr, councilmember, ...)
          - drop trailing generational/credential suffixes (jr, iii, phd, ...)
          - collapse punctuation and whitespace to single spaces
          - empty result -> NULL

        Output is the join key for exact-name blocking and the input to
        {% raw %}{{ name_phonetic_key() }}{% endraw %}. See entity-resolution-mdm.md (Layer 1).
    */
NULLIF(
    TRIM(
        REGEXP_REPLACE(                                       -- 7. collapse whitespace
            REGEXP_REPLACE(                                   -- 6. punctuation -> space
                REGEXP_REPLACE(                               -- 5. drop trailing suffix
                    REGEXP_REPLACE(                           -- 4. drop leading honorific
                        REGEXP_REPLACE(                       -- 3. flip "last, first"
                            LOWER(TRIM(UNACCENT({{ expr }}))), -- 1-2. unaccent/lower/trim
                            '^\s*([^,]+),\s*(.+)$',
                            '\2 \1'
                        ),
                        '^(mr|mrs|ms|dr|hon|rev|sen|rep|councilmember|commissioner|mayor|judge)\.?\s+',
                        '',
                        'gi'
                    ),
                    '\s+(jr|sr|ii|iii|iv|esq|phd|md)\.?$',
                    '',
                    'gi'
                ),
                '[^a-z0-9]+',
                ' ',
                'g'
            ),
            '\s+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}
