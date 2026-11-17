/*
    Data centers discussed in meeting transcripts (#445, sibling of data_center_agenda_item).
    Grain: one row per (transcript video, passage). A passage is a ~3-minute window of timed
    caption cues, or a 2,500-character window of the transcript text when it has no timing
    (int_data_center_transcript__passage).

    A row exists only when the passage's own words say "data center" / "data centre" /
    "datacenter" / "hyperscale(r)" and ts_headline produces a <mark>ed excerpt from them:
    no metadata-only matches. Place, date and title come from event_youtube_with_jurisdiction,
    so junk/non-government channels are already gated out.

    Site link (data_center_site_id, site_match_basis), best first:
      named_in_passage  the passage names a tracked site (site name or project, 6+ characters)
                        in the video's state;
      nearby_site       the video's jurisdiction is one of the governments around a site
                        (int_data_center_site__jurisdiction); when several, the one whose owner
                        is named in the passage, then by site name;
      null              a data center was discussed where no Epoch site is known.
    match_strength is site_specific when the passage names the linked site, its project or
    (for a nearby site) its owner; otherwise data_center.
    No LLM: plain Postgres text matching, rebuilt on every dbt run.
*/

{%- set dc_regex = data_center_regex() %}

with passages as (
    select * from {{ ref('int_data_center_transcript__passage') }}
),

videos as (
    select
        video_id,
        nullif(trim(video_url), '')          as video_url,
        nullif(trim(title), '')              as meeting_title,
        event_date                           as meeting_date,
        nullif(trim(jurisdiction_id), '')    as jurisdiction_id,
        nullif(trim(jurisdiction_name), '')  as jurisdiction_name,
        nullif(trim(state_code), '')         as state_code
    from {{ ref('event_youtube_with_jurisdiction') }}
    where video_id in (select video_id from passages)
),

sites as (
    select
        data_center_site_id,
        site_name,
        state_code,
        nullif(btrim(regexp_replace(owner, '\s*\((speculative|likely)\)\s*$', '', 'i')), '') as owner_term
    from {{ ref('data_center_site') }}
),

-- Site and project names a passage can name; short names are skipped so a common word can't link.
site_terms as (
    select data_center_site_id, state_code, site_name as term
    from {{ ref('data_center_site') }}
    where state_code is not null and length(site_name) >= 6
    union
    select data_center_site_id, state_code,
           btrim(regexp_replace(project, '\s*\((speculative|likely)\)\s*$', '', 'i'))
    from {{ ref('data_center_site') }}
    where state_code is not null
      and length(btrim(regexp_replace(project, '\s*\((speculative|likely)\)\s*$', '', 'i'))) >= 6
),

base as (
    select
        p.video_id,
        p.passage_index,
        p.start_seconds,
        p.passage_text,
        v.video_url,
        v.meeting_title,
        v.meeting_date,
        v.jurisdiction_id,
        v.jurisdiction_name,
        v.state_code
    from passages as p
    inner join videos as v on v.video_id = p.video_id
),

named as (
    select b.video_id, b.passage_index, t.data_center_site_id, t.term
    from base as b
    inner join site_terms as t
        on t.state_code = b.state_code
       and b.passage_text ~* ('\y' || regexp_replace(t.term, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') || '\y')
),

nearby as (
    select
        b.video_id,
        b.passage_index,
        l.data_center_site_id,
        s.site_name,
        case
            when s.owner_term is not null and length(s.owner_term) >= 4
             and b.passage_text ~* ('\y' || regexp_replace(s.owner_term, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') || '\y')
                then s.owner_term
        end as owner_named
    from base as b
    inner join {{ ref('int_data_center_site__jurisdiction') }} as l on l.jurisdiction_id = b.jurisdiction_id
    inner join sites as s on s.data_center_site_id = l.data_center_site_id
),

site_pick as (
    select distinct on (video_id, passage_index)
        video_id, passage_index, data_center_site_id, site_term, site_match_basis, is_site_specific
    from (
        select video_id, passage_index, data_center_site_id, term as site_term,
               'named_in_passage' as site_match_basis, true as is_site_specific,
               1 as pick_rank, length(term) as term_len, term as tiebreak
        from named
        union all
        select video_id, passage_index, data_center_site_id, owner_named,
               'nearby_site', owner_named is not null,
               case when owner_named is not null then 2 else 3 end, 0, site_name
        from nearby
    ) as candidates
    order by video_id, passage_index, pick_rank, term_len desc, tiebreak, data_center_site_id
),

with_evidence as (
    select
        b.*,
        sp.data_center_site_id,
        sp.site_match_basis,
        coalesce(sp.is_site_specific, false) as is_site_specific,
        sp.site_term,
        ts_headline(
            'english',
            b.passage_text,
            case
                when sp.site_term is not null
                    then {{ data_center_headline_tsquery() }} || phraseto_tsquery('english', sp.site_term)
                else {{ data_center_headline_tsquery() }}
            end,
            'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=35, MinWords=12, FragmentDelimiter=" … "'
        ) as evidence,
        array_remove(array[
            case when b.passage_text ~* '\ydata[ -]?centers?\y' then 'data center' end,
            case when b.passage_text ~* '\ydata[ -]?centres?\y' then 'data centre' end,
            case when b.passage_text ~* '\ydatacent(er|re)s?\y' then 'datacenter' end,
            case when b.passage_text ~* '\yhyperscal(e|er|ers)?\y' then 'hyperscale' end,
            sp.site_term
        ], null) as match_terms
    from base as b
    left join site_pick as sp
        on sp.video_id = b.video_id and sp.passage_index = b.passage_index
),

known_jurisdictions as (
    select jurisdiction_id, name as jurisdiction_name from {{ ref('jurisdictions') }}
)

select
    md5(e.video_id || '|' || e.passage_index::text)::text          as data_center_meeting_mention_id,
    e.video_id::text                                                as video_id,
    coalesce(e.video_url, 'https://www.youtube.com/watch?v=' || e.video_id)::text as video_url,
    e.meeting_title::text                                           as meeting_title,
    e.meeting_date::date                                            as meeting_date,
    j.jurisdiction_id::text                                         as jurisdiction_id,
    coalesce(e.jurisdiction_name, j.jurisdiction_name)::text        as jurisdiction_name,
    e.state_code::text                                              as state_code,
    (case when e.state_code is not null then {{ state_code_to_name('e.state_code') }} end)::text as state,
    e.passage_index::int                                            as passage_index,
    e.start_seconds::numeric(12, 3)                                 as start_seconds,
    e.evidence::text                                                as evidence,
    e.match_terms::text[]                                           as match_terms,
    (case when e.is_site_specific then 'site_specific' else 'data_center' end)::text as match_strength,
    e.data_center_site_id::text                                     as data_center_site_id,
    e.site_match_basis::text                                        as site_match_basis
from with_evidence as e
left join known_jurisdictions as j on j.jurisdiction_id = e.jurisdiction_id
where e.evidence like '%<mark>%'
