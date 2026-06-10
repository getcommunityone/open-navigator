-- Decisions/bills mapped to a policy question. outcome_normalized collapses the
-- free-text source outcome into a small controlled vocabulary in dbt (no Python
-- SQL logic). Decision outcomes are hundreds of free-text strings; bills (Phase 2)
-- get their own branch keyed on source_type.
with src as (
    select * from {{ source('pq_bronze', 'bronze_question_instance') }}
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
    from src
)
select * from normalized
where instance_id is not null
  and question_id is not null
