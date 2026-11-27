{{
  config(
    materialized='table',
    tags=['marts', 'bills', 'meetings', 'serving'],
    indexes=[
      {'columns': ['video_id'], 'type': 'btree'},
      {'columns': ['bill_uid'], 'type': 'btree'},
      {'columns': ['state_code', 'meeting_date'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: meeting_bill_link (#1314, porting #1072's draft meeting_bill_mention) — the state bills a meeting names.
    Grain: one row per (meeting_key, bill_uid). meeting_key = the recording's video_id, or 'doc:<event_meeting_document_id>'
    for an agenda or minutes that has no recording.

    PK  meeting_bill_link_id = md5(meeting_key | bill_uid).
    FK  bill_uid -> bills; event_meeting_id -> event_meeting (nullable); event_meeting_document_id ->
        event_meeting_document (nullable).

    A link needs evidence, never a guess (no LLM, no fuzzy title match):

      transcript  the meeting transcript (event_documents.content) says the bill: "HB 288", "H.B. 288", "House Bill 288",
                  "SB 79", "S.B. 79", "Senate Bill 79", "AB 5" / "Assembly Bill 5", "HF 12" / "House File 12",
                  "SF 3" / "Senate File 3", "LB 7" / "Legislative Bill 7". Bare one-letter forms ("H 12") are skipped:
                  too ambiguous in speech. Candidates are pre-filtered on the GIN-indexed content_tsv.
      decision    a decision's own headline or statement (event_decision) writes one of the same forms; the meeting is
                  the decision's event_meeting. A decision that cites "state law" without naming a bill is not a link:
                  there is no evidence of which bill.
      agenda /    an agenda or minutes document (event_meeting_document) writes one; the meeting is its recording when
      minutes     the document is tied to one, else the document itself.
      analysis    the AI meeting analysis's legislation number (event_policy_bill.official_number) is written as one.

    Each reference becomes (kind, number): H for house-bill forms, S senate, A assembly, HF/SF the "file" forms, LB
    Nebraska. Each OpenStates identifier is read the same way (HB/H.B./H/HF -> H, SB/S.B./S/SF -> S, AB/A -> A, plus
    HF/SF/LB for themselves), so "House Bill 12" finds "H 12" in Massachusetts and "HF 12" in Minnesota, while "House
    File 12" only finds HF bills.

    Matching: same state as the meeting, same kind and number, in a session whose year is the meeting year, else the
    year before (two-year sessions); a regular session beats a special one. No bill, no row.

    One row per (meeting, bill): match_method is the strongest source (transcript > decision > minutes > agenda >
    analysis) and match_methods lists every source that found it. match_text is a verbatim excerpt of that source with
    the reference in <mark> (a row without a <mark> is dropped). start_seconds is the caption cue where it is said,
    when the transcript has timed cues. Rule and counts: web_docs/docs/development/meeting-bill-links.md.
*/

{%- set ref_regex = "\\m(((house|senate|assembly|legislative)\\s+(bill|file)|h\\.\\s?b\\.?|s\\.\\s?b\\.?|a\\.\\s?b\\.?|hb|sb|ab|hf|sf|lb)\\s*(no\\.?\\s*|number\\s+)?0*([0-9]{1,5}))\\M" %}
{%- set ref_tsquery = "'(house <-> bill) | (senate <-> bill) | (assembly <-> bill) | (house <-> file) | (senate <-> file) | (legislative <-> bill) | hb | sb | ab | hf | sf | lb | h.b | s.b | a.b'" %}

{#- m[1] the whole reference as written, m[2] its prefix, m[3] house|senate|assembly|legislative, m[4] bill|file, m[6] the number. #}
{%- set kind_expr -%}
case
            when m[3] is not null and lower(m[4]) = 'file' then upper(left(m[3], 1)) || 'F'
            when lower(m[3]) = 'legislative' then 'LB'
            when m[3] is not null then upper(left(m[3], 1))
            when lower(m[2]) ~ '^(hf|sf|lb)' then upper(left(m[2], 2))
            else upper(left(m[2], 1))
        end
{%- endset %}

with

meetings as (
    select
        m.event_meeting_id,
        nullif(trim(m.video_id), '')                                                as video_id,
        case when m.meeting_date ~ '^\d{4}-\d{2}-\d{2}' then left(m.meeting_date, 10)::date end as meeting_date,
        m.c1_event_id
    from {{ ref('event_meeting') }} as m
),

meeting_by_video as (
    select video_id, min(event_meeting_id) as event_meeting_id
    from meetings
    where video_id is not null
    group by video_id
),

-- Every text a reference can be read from, in one shape.
transcripts as (
    select distinct on (d.video_id)
        d.video_id::text                                                            as meeting_key,
        d.video_id::text                                                            as video_id,
        null::text                                                                  as event_meeting_document_id,
        'transcript'::text                                                          as method,
        d.content,
        d.segments,
        nullif(trim(d.video_url), '')                                               as source_url,
        case when d.event_date > current_date then null else d.event_date end       as meeting_date,
        nullif(trim(d.jurisdiction_name), '')                                       as jurisdiction_name,
        nullif(trim(d.state_code), '')                                              as state_code
    from {{ ref('event_documents') }} as d
    where d.video_id is not null
      and d.state_code is not null
      and d.event_date is not null
      and d.content_tsv @@ to_tsquery('english', {{ ref_tsquery }})
    order by d.video_id, d.content_length desc nulls last
),

decisions as (
    select
        m.video_id                                                                  as meeting_key,
        m.video_id,
        null::text                                                                  as event_meeting_document_id,
        'decision'::text                                                            as method,
        concat_ws(' — ', nullif(trim(e.headline), ''), nullif(trim(e.decision_statement), '')) as content,
        null::jsonb                                                                 as segments,
        '/decisions/' || e.event_decision_id                                        as source_url,
        m.meeting_date,
        nullif(trim(e.jurisdiction_name), '')                                       as jurisdiction_name,
        nullif(trim(e.state_code), '')                                              as state_code
    from {{ ref('event_decision') }} as e
    inner join meetings as m
        on m.c1_event_id = e.c1_event_id
    where m.video_id is not null
      and e.state_code is not null
      and (coalesce(e.headline, '') || ' ' || coalesce(e.decision_statement, '')) ~* '{{ ref_regex }}'
),

documents as (
    select
        coalesce(m.video_id, 'doc:' || d.event_meeting_document_id)                 as meeting_key,
        m.video_id,
        d.event_meeting_document_id,
        case when d.document_type = 'minutes' then 'minutes' else 'agenda' end      as method,
        d.content,
        null::jsonb                                                                 as segments,
        d.document_url                                                              as source_url,
        case when d.doc_date > current_date then null else d.doc_date end           as meeting_date,
        null::text                                                                  as jurisdiction_name,
        nullif(trim(d.state_code), '')                                              as state_code
    from {{ ref('event_meeting_document') }} as d
    left join meetings as m
        on m.event_meeting_id = d.event_meeting_id
    where d.state_code is not null
      and d.doc_date is not null
      and d.content_tsv @@ to_tsquery('english', {{ ref_tsquery }})
),

texts as (
    select * from transcripts
    union all
    select * from decisions
    union all
    select * from documents
),

-- Every reference in a text, the exact words as written. One per (text, kind, number): the first.
text_refs as (
    select distinct on (t.meeting_key, t.method, t.source_url, r.ref_kind, r.ref_number)
        t.meeting_key, t.video_id, t.event_meeting_document_id, t.method, t.source_url, t.meeting_date,
        t.jurisdiction_name, t.state_code, r.said, r.ref_kind, r.ref_number, null::text as analysis_text
    from texts as t
    cross join lateral (
        select m[1] as said, {{ kind_expr }} as ref_kind, m[6]::int as ref_number
        from regexp_matches(t.content, '{{ ref_regex }}', 'gi') as m
    ) as r
    where r.ref_number > 0
    order by t.meeting_key, t.method, t.source_url, r.ref_kind, r.ref_number
),

analysis_refs as (
    select
        b.video_id::text                                                            as meeting_key,
        b.video_id::text                                                            as video_id,
        null::text                                                                  as event_meeting_document_id,
        'analysis'::text                                                            as method,
        null::text                                                                  as source_url,
        case when b.event_date > current_date then null else b.event_date end       as meeting_date,
        nullif(trim(b.jurisdiction_name), '')                                       as jurisdiction_name,
        nullif(trim(b.state_code), '')                                              as state_code,
        m[1]                                                                        as said,
        {{ kind_expr }}                                                             as ref_kind,
        m[6]::int                                                                   as ref_number,
        btrim(b.official_number) || coalesce(' — ' || nullif(btrim(b.title), ''), '') as analysis_text
    from {{ ref('event_policy_bill') }} as b
    cross join lateral regexp_matches(btrim(b.official_number), '^{{ ref_regex }}$', 'i') as m
    where b.video_id is not null
      and b.state_code is not null
),

refs as (
    select * from text_refs
    union all
    select * from analysis_refs
    where ref_number > 0
),

bill_keys as (
    select
        b.bill_uid,
        b.identifier,
        b.title,
        b.state_code,
        b.year,
        b.latest_action_date,
        coalesce(b.session_name, '') ~* '(special|extraordinary)'                   as is_special,
        k.bill_kind,
        p[2]::int                                                                   as bill_number
    from {{ ref('bills') }} as b
    cross join lateral regexp_matches(b.identifier, '^(HB|H\.B\.|H\.?|HF|SB|S\.B\.|S\.?|SF|AB|A|LB)\s*0*([0-9]{1,5})$') as p
    cross join lateral unnest(
        case
            when p[1] in ('HB', 'H.B.', 'H', 'H.') then array['H']
            when p[1] = 'HF' then array['H', 'HF']
            when p[1] in ('SB', 'S.B.', 'S', 'S.') then array['S']
            when p[1] = 'SF' then array['S', 'SF']
            when p[1] in ('AB', 'A') then array['A']
            when p[1] = 'LB' then array['LB']
        end
    ) as k(bill_kind)
    where b.state_code is not null
      and b.year is not null
),

-- Each reference's bill: same state, kind and number, the meeting year's session (else the year before).
matched as (
    select distinct on (r.meeting_key, r.method, r.source_url, r.ref_kind, r.ref_number)
        r.*,
        k.bill_uid,
        k.identifier,
        k.title                                                                     as bill_title
    from refs as r
    inner join bill_keys as k
        on k.state_code = r.state_code
       and k.bill_kind = r.ref_kind
       and k.bill_number = r.ref_number
       and k.year in (extract(year from r.meeting_date)::int, extract(year from r.meeting_date)::int - 1)
    where r.meeting_date is not null
    order by r.meeting_key, r.method, r.source_url, r.ref_kind, r.ref_number,
             (k.year = extract(year from r.meeting_date)::int) desc,
             k.is_special, k.latest_action_date desc nulls last, k.bill_uid
),

-- One row per (meeting, bill): the strongest source, with every source that found it.
methods as (
    select meeting_key, bill_uid,
           array_agg(distinct method order by method)                                as match_methods
    from matched
    group by meeting_key, bill_uid
),

per_bill as (
    select distinct on (m.meeting_key, m.bill_uid)
        m.*,
        mt.match_methods
    from matched as m
    inner join methods as mt
        on mt.meeting_key = m.meeting_key and mt.bill_uid = m.bill_uid
    order by m.meeting_key, m.bill_uid,
             array_position(array['transcript', 'decision', 'minutes', 'agenda', 'analysis'], m.method), m.said
),

with_text as (
    select p.*, t.content, t.segments
    from per_bill as p
    left join texts as t
        on t.meeting_key = p.meeting_key
       and t.method = p.method
       and t.source_url is not distinct from p.source_url
),

with_evidence as (
    select
        w.*,
        case
            when w.method = 'analysis' then regexp_replace(
                w.analysis_text,
                '^(' || regexp_replace(w.said, '([.^$*+?()\[\]{}|\\])', '\\\1', 'g') || ')',
                '<mark>\1</mark>'
            )
            else (
                select
                    case when x.pos > 221 then '…' else '' end
                    || regexp_replace(substr(w.content, greatest(1, x.pos - 220), least(x.pos, 221) - 1),
                                      case when x.pos > 221 then '^\S*\s+' else '^' end, '')
                    || '<mark>' || w.said || '</mark>'
                    || regexp_replace(substr(w.content, x.pos + length(w.said), 220), '\s+\S*$', '')
                    || case when x.pos + length(w.said) + 220 <= length(w.content) then '…' else '' end
                from (select strpos(w.content, w.said) as pos) as x
                where x.pos > 0
            )
        end                                                                         as match_text,
        '\m' || regexp_replace(
            regexp_replace(w.said, '([.^$*+?()\[\]{}|\\])', '\\\1', 'g'), '\s+', '\\s+', 'g'
        ) || '\M'                                                                   as said_regex
    from with_text as w
),

final as (
    select
        e.*,
        case when e.method = 'transcript' and jsonb_typeof(e.segments) = 'array' then (
            select (s.seg ->> 'start')::numeric
            from (
                select t.seg, t.ord, lag(t.seg ->> 'text') over (order by t.ord) as prev_text
                from jsonb_array_elements(e.segments) with ordinality as t(seg, ord)
            ) as s
            where (coalesce(s.prev_text, '') || ' ' || coalesce(s.seg ->> 'text', '')) ~* e.said_regex
              and (s.seg ->> 'start') ~ '^[0-9.]+$'
            order by s.ord
            limit 1
        ) end                                                                       as start_seconds
    from with_evidence as e
),

state_names as (
    select distinct on (state_code) state_code, state
    from {{ ref('event_documents') }}
    where state is not null and length(state) > 2 and state_code is not null
    order by state_code, state
),

-- A meeting's place when the source carried none (agendas): the transcript's, else the decision's.
places as (
    select meeting_key, max(jurisdiction_name) as jurisdiction_name
    from texts
    where jurisdiction_name is not null
    group by meeting_key
)

select
    md5(f.meeting_key || '|' || f.bill_uid)::text                                   as meeting_bill_link_id,
    f.meeting_key::text                                                             as meeting_key,
    f.video_id::text                                                                as video_id,
    mv.event_meeting_id::integer                                                    as event_meeting_id,
    f.event_meeting_document_id::text                                               as event_meeting_document_id,
    f.meeting_date::date                                                            as meeting_date,
    coalesce(f.jurisdiction_name, pl.jurisdiction_name)::text                       as jurisdiction_name,
    f.state_code::text                                                              as state_code,
    sn.state::text                                                                  as state,
    f.bill_uid::text                                                                as bill_uid,
    f.identifier::text                                                              as identifier,
    f.bill_title::text                                                              as bill_title,
    f.method::text                                                                  as match_method,
    f.match_methods::text[]                                                         as match_methods,
    f.match_text::text                                                              as match_text,
    round(f.start_seconds, 1)::numeric                                              as start_seconds,
    (case
        when f.method = 'transcript' and coalesce(f.source_url, '') like '%youtu%' and f.start_seconds is not null
            then f.source_url || (case when f.source_url like '%?%' then '&' else '?' end)
                 || 't=' || floor(f.start_seconds)::int || 's'
        when f.method in ('transcript', 'analysis') and f.video_id is not null and f.start_seconds is not null
            then 'https://www.youtube.com/watch?v=' || f.video_id || '&t=' || floor(f.start_seconds)::int || 's'
        when f.source_url is not null then f.source_url
        when f.video_id is not null then 'https://www.youtube.com/watch?v=' || f.video_id
    end)::text                                                                      as url
from final as f
left join meeting_by_video as mv
    on mv.video_id = f.video_id
left join state_names as sn
    on sn.state_code = f.state_code
left join places as pl
    on pl.meeting_key = f.meeting_key
where f.match_text like '%<mark>%'
