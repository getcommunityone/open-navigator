-- public.policy_question — the minted registry of recurring, jurisdiction-neutral
-- policy questions that local decisions (and, Phase 2, state bills) map into.
-- Rollup counts are denormalized in from int_policy_question_rollup so the API
-- can serve the comparative numbers ("32 of 47 jurisdictions approved") directly.
--
-- Two row provenances are unioned here:
--   * clustered  — LLM-minted from stg_policy_question (is_featured=false).
--   * curated    — hand-authored editorial "featured" questions from the
--                  curated_policy_questions seed (is_featured=true). These have
--                  no linked decisions, so EVERY rollup/comparative count is 0
--                  (honest empty state — no fabricated numbers; this repo forbids
--                  fabricated data). first_seen is a fixed literal, not now(), so
--                  builds stay deterministic.
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
        cast(null as integer)                          as display_order
    from q
    left join rollup r using (question_id)
),
curated as (
    select
        md5(primary_theme || '|' || canonical_text)    as question_id,
        canonical_text,
        nullif(topic_code, '')                         as topic_code,
        primary_theme,
        nullif(cofog_code, '')                         as cofog_code,
        'local'                                        as scope,
        'active'                                       as status,
        timestamptz '2026-06-11 00:00:00+00'           as first_seen,
        0                                              as member_count,
        0::integer                                     as instances_total,
        0::integer                                     as decisions_total,
        0::integer                                     as bills_total,
        0::integer                                     as jurisdictions_total,
        0::integer                                     as jurisdictions_approved,
        0::integer                                     as states_total,
        0::integer                                     as approved_count,
        0::integer                                     as denied_count,
        0::integer                                     as deferred_count,
        0::integer                                     as other_count,
        'curated'                                      as model_name,
        true                                           as is_featured,
        display_order::integer                         as display_order
    from {{ ref('curated_policy_questions') }}
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
)
select * from clustered_deduped
union all
select * from curated
