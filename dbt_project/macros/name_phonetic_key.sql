{% macro name_phonetic_key(expr) -%}
    /*
        Double-Metaphone phonetic key of the FAMILY (last) token of a name.

        Used as a fuzzy blocking key (smith/smyth, jon/john collide) and as a
        name ComparisonLevel in Splink. Requires the fuzzystrmatch extension
        (see {% raw %}{{ enable_mdm_extensions() }}{% endraw %}).

        Builds on {% raw %}{{ normalize_person_name() }}{% endraw %} so titles/suffixes are already
        stripped; '^.*\s' keeps everything after the last space (the surname),
        or the whole string when there is no space.
    */
NULLIF(
    DMETAPHONE(
        REGEXP_REPLACE({{ normalize_person_name(expr) }}, '^.*\s', '')
    ),
    ''
)
{%- endmacro %}
