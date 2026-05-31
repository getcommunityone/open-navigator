{% macro display_org_name(expr) -%}
    /*
        Display-cased organization name. IRS/NCCS nonprofit names arrive ALL
        UPPERCASE; title-case those so the golden record reads naturally. Names
        that already carry lowercase letters (correctly mixed-case, or with
        intentional acronyms) are left untouched.

        Use for the human-facing org_name column only — match on org_name_norm,
        not this. See normalize_org_name.
    */
CASE
    WHEN {{ expr }} = UPPER({{ expr }}) THEN INITCAP({{ expr }})
    ELSE {{ expr }}
END
{%- endmacro %}
