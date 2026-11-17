{#-
    Text-matching helpers for the #508 decision context marts (decision_place_label,
    decision_company_mention). Plain Postgres regex, no LLM.

    regex_escape(expr): escape a text column so it matches itself literally in a regex.

    phrase_regex(expr): a regex that finds the escaped phrase as a whole word or phrase,
        case-sensitively, with a non-alphanumeric character (or the start/end of the text)
        on both sides, so "Stack" never matches inside "Haystack" and "AWS" never inside
        "LAWS". Three groups: (1) the left boundary, (2) the phrase, (3) the right boundary.

    named_road_regex(): the road words that make a corridor, intersection or street address
        a named road ("West Samford Avenue", "Tomachici Road", "I-70"); "industrial
        corridor" or "200 West" has none. Matched case-insensitively.
-#}

{% macro regex_escape(expr) -%}
regexp_replace({{ expr }}, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g')
{%- endmacro %}

{% macro phrase_regex(expr) -%}
('(^|[^[:alnum:]])(' || {{ regex_escape(expr) }} || ')($|[^[:alnum:]])')
{%- endmacro %}

{% macro named_road_regex() -%}
\m(road|rd|street|st|avenue|ave|av|parkway|pkwy|highway|hwy|boulevard|blvd|drive|dr|lane|ln|way|pike|turnpike|route|rte|interstate|freeway|expressway|trail|trl|circle|cir|court|ct|place|pl|terrace|loop)\M|\mI-\s?\d+|\m(US|SR|state road|state route|county road|county highway|CR)\s+[0-9A-Z]+\M
{%- endmacro %}
