{% macro link_text_date_parts(text_expr) %}
{#-
    Year, month and day read from a document's link text (#1035), as int[3], or null: "Aug. 31, 2021",
    "April 30, 2026 (Special Session)", "3/12/2026", "3.12.26", "2026-03-12". Month names match on their first three
    letters; two-digit years read as 20YY. No date is built here (an impossible date such as Feb 30 must not fail the
    model); safe_date_from_parts() builds and checks it.
-#}
(
    case
        when lower({{ text_expr }}) ~ '(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}'
        then array[
            (regexp_match(lower({{ text_expr }}), '(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})'))[3]::int,
            array_position(
                array['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'],
                (regexp_match(lower({{ text_expr }}), '(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})'))[1]
            ),
            (regexp_match(lower({{ text_expr }}), '(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})'))[2]::int
        ]
        when {{ text_expr }} ~ '(19|20)\d{2}-\d{1,2}-\d{1,2}'
        then (regexp_match({{ text_expr }}, '((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})'))::int[]
        when {{ text_expr }} ~ '(^|[^0-9])\d{1,2}[./]\d{1,2}[./](\d{4}|\d{2})([^0-9]|$)'
        then array[
            case when length((regexp_match({{ text_expr }}, '(?:^|[^0-9])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:[^0-9]|$)'))[3]) = 2
                 then 2000 + (regexp_match({{ text_expr }}, '(?:^|[^0-9])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:[^0-9]|$)'))[3]::int
                 else (regexp_match({{ text_expr }}, '(?:^|[^0-9])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:[^0-9]|$)'))[3]::int end,
            (regexp_match({{ text_expr }}, '(?:^|[^0-9])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:[^0-9]|$)'))[1]::int,
            (regexp_match({{ text_expr }}, '(?:^|[^0-9])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:[^0-9]|$)'))[2]::int
        ]
    end
)
{% endmacro %}

{% macro safe_date_from_parts(parts_expr) %}
{#- A date from int[3] (year, month, day), or null when the parts don't make a real date (no error on Feb 30). -#}
(
    case
        when ({{ parts_expr }})[2] between 1 and 12 and ({{ parts_expr }})[3] between 1 and 31
             and ({{ parts_expr }})[1] between 1990 and 2035
             and extract(day from make_date(({{ parts_expr }})[1], ({{ parts_expr }})[2], 1) + (({{ parts_expr }})[3] - 1))
                 = ({{ parts_expr }})[3]
        then make_date(({{ parts_expr }})[1], ({{ parts_expr }})[2], 1) + (({{ parts_expr }})[3] - 1)
    end
)
{% endmacro %}
