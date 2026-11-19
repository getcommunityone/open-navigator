{#-
    Text-matching helpers for the #508 / #525 decision context marts (decision_place_label,
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

{#-
    Developer cues for naming a company in a meeting passage (#525). A company in a
    transcript is the decision's applicant or developer only when the passage says so
    next to the name; a company named in passing ("Google and Meta haven't come to me",
    "a Meta data center in Newton County") is another site or a hypothetical, not this one.

    cue_before_regex(term): "on behalf of X", "X" after "teamed up with", "the applicant
        is / the applicant, / applicant is", "the developer is / the developer, /
        developer is". Four groups: (1) left boundary, (2) the cue, (3) the company
        words, (4) right boundary. Use with the 'i' flag (captions are mostly lower case).

    cue_after_regex(term): "X is a ... developer / operator / owner" (up to 40 characters
        between, none of them a sentence end). Three groups: (1) left boundary, (2) the
        company words, (3) the cue.
-#}

{% macro cue_before_regex(expr) -%}
('(^|[^[:alnum:]])((?:on behalf of|teamed up with|the applicant is|the applicant,|applicant is|the developer is|the developer,|developer is)[[:space:]]+(?:the[[:space:]]+)?)(' || {{ regex_escape(expr) }} || ')($|[^[:alnum:]])')
{%- endmacro %}

{% macro cue_after_regex(expr) -%}
('(^|[^[:alnum:]])(' || {{ regex_escape(expr) }} || ')([[:space:],]+(?:is|are|was)[[:space:]]+(?:an?|the)[[:space:]]+[^.?!]{0,40}\m(?:developer|operator|owner)\M)')
{%- endmacro %}

{% macro named_road_regex() -%}
\m(road|rd|street|st|avenue|ave|av|parkway|pkwy|highway|hwy|boulevard|blvd|drive|dr|lane|ln|way|pike|turnpike|route|rte|interstate|freeway|expressway|trail|trl|circle|cir|court|ct|place|pl|terrace|loop)\M|\mI-\s?\d+|\m(US|SR|state road|state route|county road|county highway|CR)\s+[0-9A-Z]+\M
{%- endmacro %}
