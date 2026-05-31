{% macro normalize_org_name(expr) -%}
    /*
        Normalize an organization name for matching: unaccent + lowercase, strip
        punctuation, drop trailing legal suffixes (inc, llc, corp, co, ...) and a
        leading "the", collapse whitespace. Empty -> NULL.

        Used to build the deterministic org key md5(org_name_norm | state_code)
        for orgs without an EIN. See entity-resolution-mdm.md (organization pool).
    */
NULLIF(
    TRIM(
        REGEXP_REPLACE(                                           -- 5. collapse ws
            REGEXP_REPLACE(                                       -- 4. drop legal suffix(es)
                REGEXP_REPLACE(                                   -- 3. drop leading "the"
                    REGEXP_REPLACE(                               -- 2. punctuation -> space
                        LOWER(TRIM(UNACCENT({{ expr }}))),        -- 1. unaccent/lower
                        '[^a-z0-9 ]+', ' ', 'g'
                    ),
                    '^the ', '', 'g'
                ),
                ' (incorporated|corporation|company|inc|llc|llp|lp|ltd|corp|co|pllc|pc)( |$)',
                ' ', 'g'
            ),
            '\s+', ' ', 'g'
        )
    ),
    ''
)
{%- endmacro %}
