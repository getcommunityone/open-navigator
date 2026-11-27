{{ config(materialized='table', tags=['data_centers', 'meeting_comments', 'serving']) }}

/*
    Public places named in a data-center public comment (#1233 phase 1b, the owner's question
    "are we capturing addresses, locations, districts, schools ... as NER?"). Grain: one row
    per (comment, place_kind, place_name). Free, no LLM:
      * shapes in the comment's own words (seed comment_place_patterns, case-sensitive, proper
        names are capitalised in captions): roads and routes ("Route 9", "Ridge Road"),
        schools ("Oak Hill Elementary"), counties / townships, neighborhoods / subdivisions,
        districts / wards, and sites ("the Pine Ridge site");
      * a gazetteer from our own data: jurisdictions in the meeting's state (name of 5+
        characters, place_kind 'jurisdiction') and curated data_center_project names
        (place_kind 'project').
    Privacy (AGENTS.md): the segmenter replaced every home address and "I live at/on ..."
    span with "[address removed]" BEFORE storing text, so a resident's own address or street
    of residence can't be tagged here; only public places are recorded. A leading function
    word the capitalised shape swallowed ("The", "On", "I") is trimmed.
*/

-- The speaker's own name must never come back as a "place" (Jackson, John Park), or a place row joined to the
-- display name could rebuild a full name: the introduction sentence and every word of the heard name are blanked first.
with dc_raw as (
    select d.data_center_comment_id, d.state_code, f.comment_text, f.intro_name
    from {{ ref('data_center_comment') }} as d
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = d.data_center_comment_id
),

name_words as (
    select data_center_comment_id, string_agg(
        regexp_replace(w, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g'), '|'
    ) as alt
    from dc_raw
    cross join lateral regexp_split_to_table(coalesce(intro_name, ''), '\s+') as w
    where length(w) >= 2
    group by data_center_comment_id
),

dc as (
    select
        r.data_center_comment_id,
        r.state_code,
        case
            when n.alt is null then t.no_intro
            else regexp_replace(t.no_intro, '(?i)\m(' || n.alt || ')\M', ' ', 'g')
        end as comment_text
    from dc_raw as r
    left join name_words as n on n.data_center_comment_id = r.data_center_comment_id
    cross join lateral (
        select regexp_replace(
            r.comment_text,
            '(?i)\m(my\s+name(\s+is|''s)|name\s+(and|&)\s+address\s+is)\s+[^.,;!?]{0,60}',
            ' ', 'g'
        ) as no_intro
    ) as t
),

shape_hits as (
    select dc.data_center_comment_id, p.place_kind, m[1] as raw_name
    from dc
    cross join {{ ref('comment_place_patterns') }} as p
    cross join lateral regexp_matches(dc.comment_text, '(' || p.pattern || ')', 'g') as m
),

gazetteer as (
    select 'jurisdiction'::text as place_kind, name as place_name, state_code
    from {{ ref('jurisdictions') }}
    where name is not null and length(name) >= 5 and state_code is not null
    union
    select 'project', project_name, state_code
    from {{ ref('data_center_project') }}
    where project_source = 'curated' and project_name is not null and length(project_name) >= 5
),

gazetteer_hits as (
    select dc.data_center_comment_id, g.place_kind, g.place_name as raw_name
    from dc
    inner join gazetteer as g
        on (g.state_code = dc.state_code or g.place_kind = 'project')
       and strpos(dc.comment_text, g.place_name) > 0
       and dc.comment_text ~ ('\m' || regexp_replace(g.place_name, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') || '\M')
),

cleaned as (
    select
        data_center_comment_id,
        place_kind,
        btrim(regexp_replace(
            raw_name,
            '^((The|A|An|On|At|In|Of|And|I|So|But|Thank|You|My|Our|This|That|We|Off|From|To|Near|By|Along|Yes|No|Um|Uh|Okay|Well|Now|Then|Also|With|For|Like|Over|Up|Out|Just)\s+)+',
            ''
        )) as place_name
    from (select * from shape_hits union all select * from gazetteer_hits) as h
    where raw_name !~ 'address removed'
)

select
    md5(data_center_comment_id || '|' || place_kind || '|' || place_name)::text as data_center_comment_place_id,
    data_center_comment_id::text                                                as data_center_comment_id,
    place_kind::text                                                            as place_kind,
    place_name::text                                                            as place_name
from cleaned
where length(place_name) >= 3 and place_name ~ '[A-Za-z]'
  and (place_kind in ('jurisdiction', 'project') or place_name ~ '\s')  -- a lone suffix ("Road") is no place
group by data_center_comment_id, place_kind, place_name
