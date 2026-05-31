{% macro name_phonetic_first(expr) -%}
    /*
        Double-Metaphone phonetic key of the FIRST token of a name — the
        order-agnostic companion to {% raw %}{{ name_phonetic_key() }}{% endraw %} (which keys on the
        last token). Sources disagree on token order ("Smith, John" vs
        "SMITH JOHN" vs "John Smith"), so MDM emits BOTH and lets Splink's name
        comparison + blocking rules resolve order rather than guessing it here.
        See web_docs/docs/dbt/entity-resolution-mdm.md (Watch-outs: name token order).
    */
NULLIF(
    DMETAPHONE(
        REGEXP_REPLACE({{ normalize_person_name(expr) }}, '\s.*$', '')
    ),
    ''
)
{%- endmacro %}
