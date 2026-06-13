-- public.policy_question — the minted registry of recurring, jurisdiction-neutral
-- policy questions that local decisions (and, Phase 2, state bills) map into.
-- Rollup counts are denormalized in from int_policy_question_rollup so the API
-- can serve the comparative numbers ("32 of 47 jurisdictions approved") directly.
--
-- Two row provenances are unioned here:
--   * clustered  — LLM-minted from stg_policy_question (is_featured=false).
--   * curated    — hand-authored editorial "featured" questions from the
--                  curated_policy_questions seed (is_featured=true). Comparative
--                  counts come from int_policy_question_rollup over hand-verified
--                  real decisions attached via the curated_question_instance seed;
--                  a curated question with no attached instances shows an honest
--                  zero rollup (no fabricated numbers; this repo forbids fabricated
--                  data). first_seen is a fixed literal, not now(), so builds stay
--                  deterministic.
with q as (
    select * from {{ ref('stg_policy_question') }}
),
rollup as (
    select * from {{ ref('int_policy_question_rollup') }}
),
clustered as (
    select
        q.question_id,
        q.canonical_text,
        q.topic_code,
        q.primary_theme,
        q.cofog_code,
        q.scope,
        q.status,
        q.first_seen,
        q.member_count,
        coalesce(r.instances_total, 0)::integer        as instances_total,
        coalesce(r.decisions_total, 0)::integer        as decisions_total,
        coalesce(r.bills_total, 0)::integer            as bills_total,
        coalesce(r.jurisdictions_total, 0)::integer    as jurisdictions_total,
        coalesce(r.jurisdictions_approved, 0)::integer as jurisdictions_approved,
        coalesce(r.states_total, 0)::integer           as states_total,
        coalesce(r.approved_count, 0)::integer         as approved_count,
        coalesce(r.denied_count, 0)::integer           as denied_count,
        coalesce(r.deferred_count, 0)::integer         as deferred_count,
        coalesce(r.other_count, 0)::integer            as other_count,
        q.model_name,
        false                                          as is_featured,
        cast(null as integer)                          as display_order,
        coalesce(r.money_total, 0)::numeric            as money_total,
        coalesce(q.aliases, array[]::text[])           as aliases
    from q
    left join rollup r using (question_id)
),
curated_base as (
    select
        md5(primary_theme || '|' || canonical_text)    as question_id,
        canonical_text,
        nullif(topic_code, '')                         as topic_code,
        primary_theme,
        nullif(cofog_code, '')                         as cofog_code,
        display_order::integer                         as display_order,
        -- Seed stores aliases pipe-delimited ('airbnb|vrbo'); split to a text[]
        -- and trim blanks so an empty cell yields an empty array, not [''].
        coalesce(
            array(
                select trim(a)
                from unnest(string_to_array(aliases, '|')) as a
                where trim(coalesce(a, '')) <> ''
            ),
            array[]::text[]
        )                                              as aliases
    from {{ ref('curated_policy_questions') }}
),
curated as (
    select
        b.question_id,
        b.canonical_text,
        b.topic_code,
        b.primary_theme,
        b.cofog_code,
        'local'                                        as scope,
        'active'                                       as status,
        timestamptz '2026-06-11 00:00:00+00'           as first_seen,
        coalesce(r.instances_total, 0)::integer        as member_count,
        coalesce(r.instances_total, 0)::integer        as instances_total,
        coalesce(r.decisions_total, 0)::integer        as decisions_total,
        coalesce(r.bills_total, 0)::integer            as bills_total,
        coalesce(r.jurisdictions_total, 0)::integer    as jurisdictions_total,
        coalesce(r.jurisdictions_approved, 0)::integer as jurisdictions_approved,
        coalesce(r.states_total, 0)::integer           as states_total,
        coalesce(r.approved_count, 0)::integer         as approved_count,
        coalesce(r.denied_count, 0)::integer           as denied_count,
        coalesce(r.deferred_count, 0)::integer         as deferred_count,
        coalesce(r.other_count, 0)::integer            as other_count,
        'curated'                                      as model_name,
        true                                           as is_featured,
        b.display_order,
        coalesce(r.money_total, 0)::numeric            as money_total,
        b.aliases
    from curated_base b
    left join rollup r using (question_id)
),
-- Collision guard: a curated question's md5 id could theoretically already exist
-- as a clustered row (same primary_theme + canonical_text). The curated/featured
-- row wins — drop the clustered duplicate via anti-join so the union can never
-- violate the contract-enforced unique PK on question_id.
clustered_deduped as (
    select c.*
    from clustered c
    where not exists (
        select 1 from curated cur where cur.question_id = c.question_id
    )
),
-- Money & talk SHARES are "of all decisions, not just listed questions": the
-- denominators are the grand totals across every civic decision (item_
-- interestingness), so a question's bars read as its slice of all the dollars
-- moved / all the decisions made. A 1-row grand-totals CTE is cross-joined in.
unioned as (
    select * from clustered_deduped
    union all
    select * from curated
),
grand as (
    select
        nullif(sum(net_dollar_impact), 0)::numeric as g_money,
        nullif(count(*), 0)::numeric               as g_decisions
    from {{ ref('item_interestingness') }}
)
select
    u.*,
    coalesce(u.money_total / g.g_money * 100, 0)::double precision               as money_share,
    coalesce(u.instances_total::numeric / g.g_decisions * 100, 0)::double precision as talk_share
from unioned u
cross join grand g
