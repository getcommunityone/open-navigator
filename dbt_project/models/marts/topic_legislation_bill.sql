{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['topic_id', 'state_code'], 'type': 'btree'},
      {'columns': ['state_code', 'last_action_date'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: topic_legislation_bill (#1274) — OpenStates state bills about each curated topic, with a
    category from that topic's vocabulary. Grain: one row per (topic_id, bill_id).
    PK (topic_id, bill_id); FK topic_id -> civicsearch_topic; FK bill_id -> bills.bill_uid;
    FK (topic_id, category) -> topic_legislation_category.

    Every topic in the curated_topics seed is covered with no code change: its keywords column is the match list.
    Rule and hand check: web_docs/docs/development/topic-legislation-map.md.

    1. Match: a state bill (federal bills are left out) whose lowercased OpenStates subject tags + title + abstract contain one of the
       topic's keywords as whole words (an "s"/"es" plural also matches), minus the topic's drop_keywords
       (topic_legislation_scope seed). matched_term is the first keyword found.
    2. Scope (topic_legislation_scope seed): the topic's require_pattern must match (subjects + title + abstract) when set; its
       exclude_pattern and the '*' exclude_pattern must not match the title + abstract.
    3. Category (topic_legislation_rule seed), matched on title + abstract only (never the subject tags, whose
       index words such as "environmental protection" would trip the rules): the topic's own rules when it has any, else the generic '*'
       rules (restrict / support / other). The first rule, by rule_order, whose pattern matches wins. A rule with
       an empty category leaves the bill out, and so does matching no rule. Water fluoridation ends with an
       'unclear' catch-all: the bill is about fluoride in water but its text doesn't say which way, so the map
       shows its status only; other topics with their own vocabulary have no catch-all (we do not guess).
    4. Status, from the bill's own OpenStates fields:
         enacted — a chapter citation, or the latest action says signed by the governor (New Mexico: a bare
                   "Signed") / approved by governor / chaptered / act no. / public act / pub. ch. / became law /
                   effective / filed with the secretary of state; a Speaker's or Senate President's signature is not
                   enactment;
         failed  — the latest action says died / failed to pass (not a failed amendment or motion) / sine die /
                   postponed indefinitely / inexpedient / veto sustained / withdrawn by the sponsor (not "withdrawn
                   from committee") / killed / left in committee / left pending / upon adjournment / laid on the
                   table / enacting clause stricken / study order / legislative files / without further
                   action / filed with the chief clerk / held under submission; OR its session is over in our
                   data (int_bills__session_span.is_closed) without enactment;
         passed_chamber — not enacted or failed, but OpenStates records a passage vote (latest_passage_date):
                   it passed at least one chamber;
         pending — anything else (introduced, no passage or final action in our data yet).
       passed_a_chamber is true for enacted bills and for any bill with a passage vote, including one that later
       failed (OpenStates keeps the passage date).
    introduced_date / last_action_date let meetings be matched to bills by state and date window.
    url is the bill's OpenStates page, built from state, session and identifier.
*/

with

topics as (
    select
        t.topic_id::integer as topic_id,
        t.query_id::text    as topic_query_id,
        lower(trim(k))      as keyword
    from {{ ref('curated_topics') }} t
    cross join lateral regexp_split_to_table(t.keywords, '\|') k
    left join {{ ref('topic_legislation_scope') }} sc on sc.topic_query_id = t.query_id
    where trim(k) <> ''
      and lower(trim(k)) not in (
            select lower(trim(d))
            from regexp_split_to_table(coalesce(sc.drop_keywords, ''), '\|') d
      )
),

-- Keywords as regex alternatives: metacharacters escaped (e.g. "287(g)"), longest first.
escaped as (
    select topic_id, topic_query_id, keyword,
           regexp_replace(keyword, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as kw_re
    from topics
),

topic_regex as (
    select topic_id, topic_query_id,
           '\m(' || string_agg(kw_re, '|' order by length(kw_re) desc, kw_re) || ')(s|es)?\M' as rx
    from escaped
    group by topic_id, topic_query_id
),

all_regex as (
    select '\m(' || string_agg(distinct kw_re, '|') || ')(s|es)?\M' as rx from escaped
),

bill_text as (
    select
        b.bill_uid,
        b.ocd_bill_id,
        b.identifier,
        b.title,
        b.session_identifier,
        b.session_name,
        b.state_code,
        b.latest_action_date,
        b.latest_action_description,
        b.year,
        lower(coalesce(b.title, '') || ' ' || coalesce(a.abstract_text, '')) as cat_txt,
        -- Subject tags first, so a short title ("Fluoride Amendments") sits next to a "Water" tag for the scope rule.
        lower(
            coalesce((
                select string_agg(sj, ' ')
                from jsonb_array_elements_text(case when jsonb_typeof(b.subject) = 'array' then b.subject else '[]'::jsonb end) sj
            ), '')
            || ' ' || coalesce(b.title, '') || ' ' || coalesce(a.abstract_text, '')
        ) as txt
    from {{ ref('bills') }} b
    left join {{ ref('stg_openstates__bill_abstract') }} a on a.ocd_bill_id = b.ocd_bill_id
    where b.state_code is not null
      -- Hawaii's "GM" items are the governor's nominations for confirmation, not bills.
      and coalesce(b.identifier, '') !~ '^GM '
),

candidates as (
    -- One pass over every state bill with all topics' keywords at once; per-topic matching runs on the few
    -- thousand candidates only.
    select bt.* from bill_text bt
    where bt.txt ~ (select rx from all_regex)
),

matched as (
    select c.*, tr.topic_id, tr.topic_query_id, (regexp_match(c.txt, tr.rx))[1] as matched_term
    from candidates c
    join topic_regex tr on c.txt ~ tr.rx
),

scoped as (
    select m.*
    from matched m
    left join {{ ref('topic_legislation_scope') }} s on s.topic_query_id = m.topic_query_id
    left join {{ ref('topic_legislation_scope') }} g on g.topic_query_id = '*'
    where (nullif(s.require_pattern, '') is null or m.txt ~ s.require_pattern)
      and (nullif(s.exclude_pattern, '') is null or m.cat_txt !~ s.exclude_pattern)
      and (nullif(g.exclude_pattern, '') is null or m.cat_txt !~ g.exclude_pattern)
),

rule_set as (
    -- Which rule set a topic uses: its own when the seed has rules for it, else the generic '*'.
    select t.topic_query_id,
           case when exists (select 1 from {{ ref('topic_legislation_rule') }} r where r.topic_query_id = t.topic_query_id)
                then t.topic_query_id else '*' end as rules_for
    from (select distinct topic_query_id from topics) t
),

categorised as (
    select s.*, pick.category
    from scoped s
    join rule_set rs on rs.topic_query_id = s.topic_query_id
    left join lateral (
        select nullif(r.category, '') as category
        from {{ ref('topic_legislation_rule') }} r
        where r.topic_query_id = rs.rules_for
          and s.cat_txt ~ r.pattern
        order by r.rule_order
        limit 1
    ) pick on true
    where pick.category is not null
),

statused as (
    select
        c.*,
        st.first_action_date,
        case
            when exists (
                    select 1 from jsonb_array_elements(case when jsonb_typeof(st.citations) = 'array' then st.citations else '[]'::jsonb end) ci
                    where ci ->> 'citation_type' = 'chapter'
                 )
              -- A governor's signature, never a presiding officer's ("Signed by the Speaker" happens at enrollment, before
              -- the governor acts). New Mexico records the governor's signature as a bare "Signed".
              or coalesce(c.latest_action_description, '') ~* '(signed by (the )?gov|governor signed|gov\w*\.? signed|^signed\.?$|signed chap|approved by (the )?governor|chaptered|act no\.|public act|pub\. ch|became law|becomes law|effective|filed with (the )?secretary of state)'
              then 'enacted'
            -- Only actions that end the bill: a withdrawal by its sponsor (not North Carolina's "Withdrawn From Com/Cal",
              -- which moves it), a failed passage vote (not a failed amendment or motion), being laid on the table.
            when coalesce(c.latest_action_description, '') ~* '(died|\mfailed (to pass|to concur|in |on (second|third|final)|passage)|^failed\.?$|sine die|indefinitely postponed|postponed indefinitely|inexpedient|veto sustained|withdrawn by (the )?(sponsor|author)|^withdrawn\.?$|; withdrawn\.?$|withdrawn prior to|withdrawn from consideration|killed|left in committee|left pending|upon adjournment|laid on (the )?table|enacting clause stricken|study order|legislative files|without further action|filed with the chief clerk|held under submission)'
              and coalesce(c.latest_action_description, '') !~* '(amendment\S*|motion)\s+(\S+\s+){0,3}failed'
              then 'failed'
            when ss.is_closed
              then 'failed'
            when st.latest_passage_date is not null
              then 'passed_chamber'
            else 'pending'
        end as status,
        (st.latest_passage_date is not null) as has_passage
    from categorised c
    left join {{ ref('stg_openstates__bill') }} st on st.ocd_bill_id = c.ocd_bill_id
    left join {{ ref('int_bills__session_span') }} ss
           on ss.state_code = c.state_code and ss.session_identifier is not distinct from c.session_identifier
)

select
    s.topic_id::integer                                             as topic_id,
    s.topic_query_id::text                                          as topic_query_id,
    s.bill_uid::text                                                as bill_id,
    s.ocd_bill_id::text                                             as ocd_bill_id,
    s.state_code::text                                              as state_code,
    {{ state_code_to_name('s.state_code') }}::text                  as state,
    s.identifier::text                                              as identifier,
    s.title::text                                                   as title,
    s.session_identifier::text                                      as session,
    s.session_name::text                                            as session_name,
    s.category::text                                                as category,
    s.status::text                                                  as status,
    (s.has_passage or s.status = 'enacted')::boolean                as passed_a_chamber,
    s.matched_term::text                                            as matched_term,
    s.first_action_date::date                                       as introduced_date,
    s.latest_action_date::date                                      as last_action_date,
    s.latest_action_description::text                               as last_action_description,
    s.year::integer                                                 as year,
    (
        'https://openstates.org/' || lower(s.state_code) || '/bills/'
        || replace(s.session_identifier, ' ', '%20') || '/'
        || replace(s.identifier, ' ', '') || '/'
    )::text                                                         as url,
    current_timestamp                                               as dbt_loaded_at
from statused s
