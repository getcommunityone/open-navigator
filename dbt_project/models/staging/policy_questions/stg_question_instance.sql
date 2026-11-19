-- Decisions/bills mapped to a policy question. outcome_normalized collapses the
-- free-text source outcome into a small controlled vocabulary in dbt (no Python
-- SQL logic). Decision outcomes are hundreds of free-text strings; bills (Phase 2)
-- get their own branch keyed on source_type.
--
-- Local-decision outcome families, matched in this order (first hit wins):
--   deferred   — deferral/tabling/continuance/first reading/referral wording.
--   denied     — denial/rejection/failure wording.
--   moratorium — (#483) an ADOPTED or RECOMMENDED moratorium: outcome_raw names
--                a moratorium, or the decision's own headline/statement says a
--                moratorium was adopted/approved/enacted/imposed/extended/
--                recommended; AND outcome_raw is approval-family wording (or
--                "recommend"). Matched before `approved`, because an adopted
--                moratorium pauses the thing — counting it as "approved" inverts
--                the meaning. A moratorium only proposed, considered or discussed
--                (e.g. "Moratorium proposed") is NOT moratorium: it falls through
--                to deferred/other by its outcome wording. Lifting, ending,
--                repealing or rescinding a moratorium is never moratorium.
--   approved   — approval/adoption/passage wording.
--   other      — everything else (discussion, information, public comment).
-- The decision text comes from event_decision (source_id = event_decision_id).
with src as (
    select
        instance_id, question_id, source_type, source_id, state_code,
        jurisdiction_name, city, outcome_raw, occurred_at, session, assign_score
    from {{ source('pq_bronze', 'bronze_question_instance') }}

    union all

    -- Curated, hand-verified real decisions attached to featured questions
    -- (curated_question_instance seed). instance_id mirrors the clustered
    -- convention db.md5(LOCAL_DECISION, source_id, question_id). These survive
    -- the LLM clustering rebuild, which truncates only the bronze_* tables.
    select
        md5('local_decision' || '|' || source_id || '|' || question_id) as instance_id,
        question_id,
        'local_decision'                                                as source_type,
        source_id,
        nullif(state_code, '')                                          as state_code,
        nullif(jurisdiction_name, '')                                   as jurisdiction_name,
        nullif(city, '')                                                as city,
        nullif(outcome_raw, '')                                         as outcome_raw,
        occurred_at::timestamptz                                        as occurred_at,
        null::text                                                      as session,
        1.0::double precision                                           as assign_score
    from {{ ref('curated_question_instance') }}
),
-- #501: jurisdiction_name must be a display name, never an id. Some clustered
-- rows carry the jurisdiction id instead (`chilton_01021`, `c-AL-01021`). These
-- rows have no jurisdiction_id column, but the id-shaped name IS the id, so it is
-- resolved against int_jurisdictions: a slug id by jurisdiction_id, a legacy
-- `c-{USPS}-{geoid}` county code by county geoid. Unresolvable ids become NULL.
juris as (
    select jurisdiction_id, geoid, name, jurisdiction_type
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_id is not null
),
src_named as (
    select
        s.instance_id, s.question_id, s.source_type, s.source_id, s.state_code,
        {{ heal_jurisdiction_name('s.jurisdiction_name', none, 'coalesce(j_id.name, j_cty.name)') }}
            as jurisdiction_name,
        s.city, s.outcome_raw, s.occurred_at, s.session, s.assign_score
    from src s
    left join juris j_id
      on j_id.jurisdiction_id = s.jurisdiction_name
    left join juris j_cty
      on s.jurisdiction_name ~ {{ jurisdiction_county_code_regex() }}
     and j_cty.jurisdiction_type = 'county'
     and j_cty.geoid = substring(s.jurisdiction_name from '^c-[A-Z]{2}-([0-9]+)$')
),
-- Headline + statement of the underlying local decision, for the moratorium
-- family only. One row per event_decision_id; null for bills.
decision_text as (
    select distinct on (event_decision_id)
        event_decision_id,
        coalesce(headline, '') || ' ' || coalesce(decision_statement, '') as txt
    from {{ ref('event_decision') }}
    order by event_decision_id, extracted_at desc
),
flagged as (
    select
        s.*,
        (
            s.outcome_raw ~* 'moratori'
            or dt.txt ~* '(adopt|approv|enact|impos|establish|exten|recommend|pass|plac|declar)\w*\s+(\S+\s+){0,6}moratori'
            or dt.txt ~* 'moratori\w*\s+(\S+\s+){0,6}(adopt|approv|enact|pass|exten|impos)'
        )
        and coalesce(s.outcome_raw, '') !~* '\m(lift|ends?|ending|ended|repeal|rescind|terminat)\w*\s+(\S+\s+){0,3}moratori'
        and coalesce(dt.txt, '') !~* '\m(lift|ends?|ending|ended|repeal|rescind|terminat)\w*\s+(\S+\s+){0,3}moratori'
            as names_moratorium
    from src_named s
    left join decision_text dt
      on s.source_type = 'local_decision'
     and dt.event_decision_id = s.source_id
),
normalized as (
    select
        instance_id,
        question_id,
        source_type,
        source_id,
        state_code,
        jurisdiction_name,
        city,
        outcome_raw,
        occurred_at,
        session,
        assign_score,
        case
            when source_type = 'local_decision' then
                case
                    when outcome_raw is null then 'other'
                    when outcome_raw ilike '%defer%' or outcome_raw ilike '%tabl%'
                         or outcome_raw ilike '%postpon%' or outcome_raw ilike '%continu%'
                         or outcome_raw ilike '%carried over%' or outcome_raw ilike '%held%'
                         or outcome_raw ilike '%remand%' or outcome_raw ilike '%delay%'
                         or outcome_raw ilike '%pending%' or outcome_raw ilike '%first read%'
                         or outcome_raw ilike '%second read%' or outcome_raw ilike '%introduced%'
                         or outcome_raw ilike '%referred%' or outcome_raw ilike '%scheduled%'
                         or outcome_raw ilike '%under review%' or outcome_raw ilike '%under advisement%'
                         or outcome_raw ilike '%taken under%' then 'deferred'
                    when outcome_raw ilike '%deni%' or outcome_raw ilike '%reject%'
                         or outcome_raw ilike '%defeat%' or outcome_raw ilike '%fail%'
                         or outcome_raw ilike '%disallow%' or outcome_raw ilike '%not to proceed%'
                         or outcome_raw ilike '%revoked%' or outcome_raw ilike '%upheld denial%' then 'denied'
                    when names_moratorium and (
                         outcome_raw ilike '%recommend%'
                         or outcome_raw ilike '%approv%' or outcome_raw ilike '%adopt%'
                         or outcome_raw ilike '%pass%' or outcome_raw ilike '%enact%'
                         or outcome_raw ilike '%authoriz%' or outcome_raw ilike '%ratif%'
                         or outcome_raw ilike '%carried%' or outcome_raw ilike '%ordained%'
                    ) then 'moratorium'
                    when outcome_raw ilike '%approv%' or outcome_raw ilike '%adopt%'
                         or outcome_raw ilike '%pass%' or outcome_raw ilike '%grant%'
                         or outcome_raw ilike '%authoriz%' or outcome_raw ilike '%award%'
                         or outcome_raw ilike '%ratif%' or outcome_raw ilike '%accepted%'
                         or outcome_raw ilike '%carried%' or outcome_raw ilike '%enacted%'
                         or outcome_raw ilike '%ordained%' or outcome_raw ilike '%appointed%'
                         or outcome_raw ilike '%elected%' then 'approved'
                    else 'other'
                end
            when source_type = 'state_bill' then
                case
                    when outcome_raw is null then 'pending'
                    when outcome_raw ilike '%enact%' or outcome_raw ilike '%assigned act%'
                         or outcome_raw ilike '%became law%' or outcome_raw ilike '%signed by%'
                         or outcome_raw ilike '%approved by the governor%' then 'enacted'
                    when outcome_raw ilike '%veto%' then 'vetoed'
                    when outcome_raw ilike '%indefinitely postpone%'
                         or outcome_raw ilike '%postponed indefinitely%' then 'failed'
                    when outcome_raw ilike '%carried over%' then 'carried_over'
                    when outcome_raw ilike '%died%' or outcome_raw ilike '%failed%'
                         or outcome_raw ilike '%rejected%' then 'died_in_committee'
                    else 'pending'
                end
            else 'pending'
        end as outcome_normalized
    from flagged
)
select * from normalized
where instance_id is not null
  and question_id is not null
