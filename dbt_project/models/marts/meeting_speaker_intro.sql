{{ config(
    materialized='table',
    indexes=[{'columns': ['video_id', 'char_offset'], 'type': 'btree'}],
    tags=['marts', 'transcripts', 'speakers'],
    contract={'enforced': true}
) }}

/*
    meeting_speaker_intro (#1231): who introduced themselves in a recording, in the form we may show.
    Grain: one row per self-introduction (stg_bronze_meeting_speaker_intro). PK meeting_speaker_intro_id.

    speaker_kind, decided in this order:
      suppressed  the speaker's next words say they are a student, in a grade or school, or under 18
                  (suppressed_reason 'student_or_minor'); or a resident speaking at a school board meeting
                  (jurisdiction_type school_district; a jurisdiction named for a school, ISD, USD or board of
                  education; or a title naming a school(s) board, school district, school committee, board of ed,
                  BOE, USD/ISD or students; 'school_board_meeting'). No name is shown (AGENTS.md: minors and
                  students). An unknown meeting type is not a school board; the title and name checks still apply.
      official    a "my name is" / "I'm ... I live" introduction (never a greeting or chair call, which can name
                someone else) whose first and last name equal exactly one current official of the meeting's own government
                  (person_government, office 'government', same state, jurisdiction "<name> Government"):
                  shown by full name and title from our officials data (public role).
      unrecognized the first word heard is not a known given name (mdm_person given names carried by 4+ people, or an
                official's first name): no name, because it may be an ordinary word ("my name is spelled wrong").
    resident    everyone else: "First L." from the words heard (two words -> "Jane D."; one or three words ->
                  the first name only, so a middle name is never shown as the surname). Role "Resident" only
                  when the introduction says they live here; otherwise null.
    No full private name is stored here or served: only speaker_display_name.
    Design: web_docs/docs/development/speaker-names-from-self-introductions.md
*/

with intro as (
    select * from {{ ref('stg_bronze_meeting_speaker_intro') }}
),

meeting as (
    select distinct on (d.video_id)
        d.video_id,
        d.state_code,
        d.jurisdiction_name,
        d.jurisdiction_type,
        d.event_title
    from {{ ref('event_documents') }} as d
    where d.document_type = 'transcript'
      and d.video_id in (select video_id from intro)
    order by d.video_id, d.content_length desc nulls last
),

official as (
    select
        p.person_id,
        p.full_name,
        nullif(btrim(p.title), '') as title,
        p.state_code,
        lower(btrim(regexp_replace(p.jurisdiction, '\s+government$', '', 'i'))) as jurisdiction_key,
        string_to_array(
            btrim(regexp_replace(regexp_replace(lower(p.full_name), '[^a-z \-'']', ' ', 'g'), '\s+', ' ', 'g')),
            ' '
        ) as name_words
    from {{ ref('person_government') }} as p
    where p.office = 'government'
      and coalesce(p.is_current, true)
      and p.full_name is not null
),

-- A resident's first word must be a known given name (#1231 review): captions are lower-case, so "my name is spelled
-- wrong" would otherwise serve "Spelled W.". Known = a given name at least 4 people carry in the person master
-- (an aggregate of first names only, nothing about anyone), or the first name of an official.
given_name as (
    select p.given_name_norm as given_name
    from {{ ref('mdm_person') }} as p
    where p.given_name_norm ~ '^[a-z]{2,}$'
    group by p.given_name_norm
    having count(*) >= 4
    union
    select o.name_words[1]
    from official as o
    where o.name_words[1] ~ '^[a-z]{2,}$'
),

official_match as (
    select
        i.video_id,
        i.char_offset,
        i.pattern_id,
        min(o.person_id) as person_id,
        count(distinct o.person_id) as n_matches
    from intro as i
    join meeting as m on m.video_id = i.video_id
    join official as o
        on o.state_code = m.state_code
       and o.jurisdiction_key = lower(btrim(m.jurisdiction_name))
       and i.name_token_count >= 2
       -- Only the speaker's own "my name is" / "I'm ... I live": a greeting or chair call can name someone else.
       and i.pattern_id in ('my_name_is', 'i_am_live')
       and o.name_words[1] = i.name_tokens[1]
       and o.name_words[array_length(o.name_words, 1)] = i.name_tokens[i.name_token_count]
    group by 1, 2, 3
),

classified as (
    select
        i.*,
        m.state_code,
        m.jurisdiction_name,
        case when om.n_matches = 1 then om.person_id end as person_id,
        coalesce(
            m.jurisdiction_type = 'school_district'
            or coalesce(m.jurisdiction_name, '') ~* '(school|\misd\M|\musd\M|board\s+of\s+ed)'
            or coalesce(m.event_title, '') ~* ('(schools?\s+board|school\s+district|school\s+committee|board\s+of\s+ed'
                || '|\mboe\M|\musd\M|\misd\M|board\s+of\s+trustees.*school|student)'),
            false
        ) as is_school_board,
        exists (select 1 from given_name as g where g.given_name = i.name_tokens[1]) as is_given_name
    from intro as i
    left join meeting as m on m.video_id = i.video_id
    left join official_match as om
        on om.video_id = i.video_id and om.char_offset = i.char_offset and om.pattern_id = i.pattern_id
)

select
    md5(c.video_id || '|' || c.char_offset::text || '|' || c.pattern_id)::text as meeting_speaker_intro_id,
    c.video_id::text                    as video_id,
    c.char_offset::integer              as char_offset,
    c.start_seconds::numeric(10, 3)     as start_seconds,
    c.pattern_id::text                  as pattern_id,
    c.confidence::numeric(3, 2)         as confidence,
    c.state_code::text                  as state_code,
    c.jurisdiction_name::text           as jurisdiction_name,
    (case
        when c.mentions_minor then 'suppressed'
        when o.person_id is not null then 'official'
        when c.is_school_board then 'suppressed'
        when not c.is_given_name then 'unrecognized'
        else 'resident'
    end)::text                          as speaker_kind,
    (case
        when c.mentions_minor then 'student_or_minor'
        when o.person_id is not null then null
        when c.is_school_board then 'school_board_meeting'
    end)::text                          as suppressed_reason,
    (case
        when c.mentions_minor then null
        when o.person_id is not null then o.full_name
        when c.is_school_board then null
        when not c.is_given_name then null
        when c.name_token_count = 2
            then initcap(c.name_tokens[1]) || ' ' || upper(left(c.name_tokens[2], 1)) || '.'
        else initcap(c.name_tokens[1])
    end)::text                          as speaker_display_name,
    (case
        when c.mentions_minor then null
        when o.person_id is not null then o.title
        when c.is_school_board then null
        when not c.is_given_name then null
        when c.says_resident then 'Resident'
    end)::text                          as speaker_role,
    (case when not c.mentions_minor then o.person_id end)::text as person_id
from classified as c
left join official as o on o.person_id = c.person_id
