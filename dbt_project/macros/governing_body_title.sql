{#-
    Meeting title -> words that can name a governing body (#1442).

    SQL twin of packages/ingestion/src/ingestion/governance/body_titles.py (clean_title, display_name, slug). The
    regexes are byte-identical; pytest pins the Python on real titles and the singular test
    assert_governing_body_title_examples pins this SQL on the same example seed. Change both together.

    clean_meeting_title_for_body(title, jurisdiction_name) returns lower-case, single-spaced text:
      1. drop bracketed text, dates, times, years and apostrophes; every other non [a-z0-9&] run becomes a space;
         weekday names go;
      2. drop a leading "city of " / "county of " ...;
      3. drop the jurisdiction's own base name at the start ("tuscaloosa city council" -> "city council");
      4. drop filler words ("meeting", "regular", "livestream", ...) and dangling small words.
-#}

{% macro body_title_month_re() -%}
(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?
{%- endmacro %}

{% macro body_title_base_name(jurisdiction_name) -%}
btrim(regexp_replace(regexp_replace(
    btrim(regexp_replace(lower(coalesce({{ jurisdiction_name }}, '')), '[^a-z0-9&]+', ' ', 'g')),
    '( city| county)?( school district| schools)$', ''),
    ' (county|parish|borough|city|town|village|township|cdp|ccd|municipality)$', ''))
{%- endmacro %}

{% macro body_title_pre(title) -%}
{%- set m = body_title_month_re() -%}
btrim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
    lower(coalesce({{ title }}, '')),
    '[\(\[][^\)\]]*[\)\]]', ' ', 'g'),
    '{{ m }} [0-9]{1,2}(st|nd|rd|th)?,? [0-9]{4}', ' ', 'g'),
    '[0-9]{1,2}(st|nd|rd|th)? {{ m }},? [0-9]{4}', ' ', 'g'),
    '{{ m }} [0-9]{1,2}(st|nd|rd|th)?', ' ', 'g'),
    '{{ m }},? [0-9]{4}', ' ', 'g'),
    '[0-9]{4}[/.-][0-9]{1,2}[/.-][0-9]{1,2}', ' ', 'g'),
    '[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}', ' ', 'g'),
    '[0-9]{1,2}[/.-][0-9]{1,2}', ' ', 'g'),
    '[0-9]{1,2}(:[0-9]{2})? ?(am|pm|a\.m\.|p\.m\.)', ' ', 'g'),
    '(19|20)[0-9]{2}', ' ', 'g'),
    '[''’]s( |$)', ' ', 'g'),
    '[''’]', '', 'g'),
    '[^a-z0-9&]+', ' ', 'g'),
    '(^| )(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)( |$)', ' ', 'g'),
    ' +', ' ', 'g'))
{%- endmacro %}

{% macro body_title_state_prefix_re() -%}
^(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|al|ak|az|ar|ca|co|ct|de|dc|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)( |$)
{%- endmacro %}

{% macro body_title_filler_re() -%}
(^| )(regular session|special session|business session|voting session|executive session|closed session|public hearing|live stream|no audio|in person|of the city|of the town|part [0-9]+|pt [0-9]+|day [0-9]+|livestreamed|livestream|streaming|stream|live|meetings|meeting|mtg|regular|special|called|recessed|adjourned|reconvened|continued|emergency|rescheduled|scheduled|agenda|minutes|video|recording|replay|official|monthly|quarterly|annual|joint|hearing|edited|full|archived|archive|audio|zoom|virtual|hybrid)(?= |$)
{%- endmacro %}

{% macro clean_meeting_title_for_body(title, jurisdiction_name) -%}
(
    select btrim(regexp_replace(regexp_replace(
        btrim(regexp_replace(regexp_replace(
            case
                when position(' ' in s.u) > 0 then regexp_replace(s.u, '{{ body_title_state_prefix_re() }}', '')
                else s.u
            end,
            '{{ body_title_filler_re() }}', ' ', 'g'),
            ' +', ' ', 'g')),
        '^(the|and|of|for|at|on) ', ''),
        ' (and|of|for|at|on|the)$', ''))
    from (
        select
            case
                when x.b <> '' and (x.t = x.b or left(x.t, length(x.b) + 1) = x.b || ' ')
                    then btrim(substr(x.t, length(x.b) + 1))
                else x.t
            end as u
        from (
            select
                regexp_replace({{ body_title_pre(title) }}, '^(the )?((city|town|village|borough|township|county|parish) of )', '') as t,
                {{ body_title_base_name(jurisdiction_name) }} as b
        ) as x
    ) as s
)
{%- endmacro %}

{#- "planning and zoning" -> "Planning and Zoning": each word capitalised, small words after the first kept. -#}
{% macro body_display_name(cleaned) -%}
(
    select string_agg(
        case when u.o > 1 and u.w in ('and', 'of', 'the', 'for', 'on', 'at', 'to', 'in') then u.w
             else upper(left(u.w, 1)) || substr(u.w, 2) end,
        ' ' order by u.o)
    from unnest(string_to_array({{ cleaned }}, ' ')) with ordinality as u(w, o)
)
{%- endmacro %}

{% macro body_slug(cleaned) -%}
btrim(regexp_replace(replace({{ cleaned }}, '&', ' and '), '[^a-z0-9]+', '_', 'g'), '_')
{%- endmacro %}

{#- Seed applies_to family for a jurisdiction type. -#}
{% macro body_jurisdiction_kind(jurisdiction_type) -%}
(case when lower(coalesce({{ jurisdiction_type }}, '')) in ('county', 'school_district', 'state')
      then lower({{ jurisdiction_type }}) else 'municipal' end)
{%- endmacro %}

{#-
    resolve_governing_body(relation): for each distinct (cleaned, kind) in `relation` (a CTE name), the first seed
    pattern by priority whose applies_to fits, resolved to body_key / body_type / body_name. __skip__ rows are dropped
    (no body). Shared by int_meeting_body__matched and the example test so both resolve identically.
-#}
{% macro resolve_governing_body(relation) -%}
select
    f.cleaned,
    f.kind,
    f.pattern_id,
    case
        when f.body_key = '__generic__' then f.body_type || ':' || {{ body_slug('f.cleaned') }}
        when f.kind = 'school_district' and f.body_key = 'governing_body' then 'school_board'
        else f.body_key
    end                                                 as body_key,
    case
        when f.kind = 'school_district' and f.body_key = 'governing_body' then 'school_board'
        else f.body_type
    end                                                 as body_type,
    case
        when f.body_key = '__generic__' then {{ body_display_name('f.cleaned') }}
        when nullif(f.body_name, '') is not null then f.body_name
        when f.name_from_title
            then {{ body_display_name("btrim((regexp_match(f.cleaned, '(' || f.pattern || ')'))[1])") }}
    end                                                 as body_name
from (
    select distinct on (d.cleaned, d.kind)
        d.cleaned,
        d.kind,
        p.pattern_id,
        p.pattern,
        p.body_key,
        p.body_name,
        p.body_type,
        p.name_from_title
    from (select distinct cleaned, kind from {{ relation }} where cleaned <> '') as d
    join {{ ref('governing_body_pattern') }} as p
        on p.applies_to in ('any', d.kind)
       and d.cleaned ~ p.pattern
    order by d.cleaned, d.kind, p.priority, p.pattern_id
) as f
where f.body_key <> '__skip__'
{%- endmacro %}
