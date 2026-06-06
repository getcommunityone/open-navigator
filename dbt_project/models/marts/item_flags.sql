{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'flags'],
        contract={'enforced': true}
    )
}}

/*
public.item_flags — "Raised Eyebrows" anomaly scaffold. One row per (subject, flag).

CRITICAL SEMANTICS: every row is an UNVERIFIED ANOMALY, NOT a finding or an
accusation. Flags are review prompts; a human must verify against the linked
source_record_url before any conclusion. This is kept deliberately SEPARATE from
item_interestingness — anomalies have different (review-sensitive) semantics and
must never inflate the discovery score.

Each detector is gated by its own feature-flag var (default OFF). Most detectors
need a data source this warehouse does NOT have yet (district boundaries, vendor
/ contract awards, economic-interest filings, member reimbursements); those are
left as documented TODO detectors behind their flag so the model still BUILDS and
emits a stable, contract-enforced schema (0 rows until the source + flag land).
The one detector the data supports today — threshold_structuring over
event_financial_item amounts — is implemented and gated by
civic_flag_threshold_structuring (default OFF until per-jurisdiction approval
limits are configured rather than a single global var).

Reuses existing models only (event_financial_item, event_decision, the mdm_bridge_*
Splink xref). Does NOT build a new entity matcher.

Detectors (status):
  threshold_structuring  IMPLEMENTED (global-limit approximation; flag-gated)
  residency_mismatch     TODO — needs district-boundary geometry (no PostGIS source)
  vendor_official_tie    TODO — needs vendor/contract awards to join to mdm_bridge_* xref
  expense_outlier        TODO — needs member reimbursement data
  sole_source_concentration TODO — needs no-bid/sole-source award data
  late_disclosure        TODO — needs economic-interest filing data
*/

with
-- Typed schema template; guarantees the contract columns exist even when every
-- detector is disabled. Emits no rows.
template as (
    select
        cast(null as text)             as flag_type,
        cast(null as text)             as subject_ref,
        cast(null as text)             as subject_kind,
        cast(null as text)             as state_code,
        cast(null as double precision) as severity,
        cast(null as jsonb)            as evidence,
        cast(null as text)             as source_record_url
    where false
),

{% if var('civic_flag_threshold_structuring', false) %}
-- award/purchase amount sitting just below a configured approval limit; severity
-- rises the closer it sits to the limit (the classic structuring signature).
threshold_structuring as (
    select
        'threshold_structuring'                          as flag_type,
        f.event_financial_item_id                        as subject_ref,
        'financial_item'                                 as subject_kind,
        f.state_code,
        -- 0 at the band floor, ->1 right under the limit
        least(1.0, greatest(0.0,
            1.0 - (({{ var('civic_approval_limit', 50000) }} - f.amount)
                   / ({{ var('civic_approval_limit', 50000) }} * {{ var('civic_structuring_band', 0.1) }}))
        ))                                               as severity,
        jsonb_build_object(
            'amount', f.amount,
            'approval_limit', {{ var('civic_approval_limit', 50000) }},
            'pct_below_limit', round((({{ var('civic_approval_limit', 50000) }} - f.amount)
                                       / {{ var('civic_approval_limit', 50000) }} * 100)::numeric, 2),
            'note', 'Unverified anomaly: amount within configured band below the approval limit.'
        )                                                as evidence,
        '/meetings/' || f.analysis_id                    as source_record_url
    from {{ ref('event_financial_item') }} f
    where f.amount is not null
      and f.amount <  {{ var('civic_approval_limit', 50000) }}
      and f.amount >= {{ var('civic_approval_limit', 50000) }} * (1 - {{ var('civic_structuring_band', 0.1) }})
),
{% endif %}

all_flags as (
    select * from template
    {% if var('civic_flag_threshold_structuring', false) %}
    union all select * from threshold_structuring
    {% endif %}
    -- TODO(residency_mismatch): union a detector here once district-boundary
    --   geometry exists; point-in-polygon of official address vs represented
    --   district, severity by distance outside the line. Gate: civic_flag_residency_mismatch.
    -- TODO(vendor_official_tie): join awarded-vendor principals/address to a sitting
    --   member via mdm_bridge_* (existing Splink xref) with no recorded recusal.
    --   Gate: civic_flag_vendor_official_tie. Needs an award/contract source.
    -- TODO(expense_outlier): robust z-score of a member's reimbursements vs peers.
    --   Gate: civic_flag_expense_outlier. Needs member-expense data.
    -- TODO(sole_source_concentration): one vendor's share of no-bid awards over the
    --   window. Gate: civic_flag_sole_source_concentration. Needs award data.
    -- TODO(late_disclosure): required economic-interest filing missing/past statutory
    --   window. Gate: civic_flag_late_disclosure. Needs filing data.
),

deduped as (
    select
        md5(flag_type || '|' || subject_ref) as item_flag_id,
        flag_type,
        subject_ref,
        subject_kind,
        state_code,
        severity,
        evidence,
        source_record_url,
        -- per-subject rollup for the Raised Eyebrows lens sort
        max(severity) over (partition by subject_ref)  as anomaly_score,
        true                                            as anomaly_any
    from all_flags
)

select
    item_flag_id::text                  as item_flag_id,
    flag_type::text                     as flag_type,
    subject_ref::text                   as subject_ref,
    subject_kind::text                  as subject_kind,
    state_code::text                    as state_code,
    severity::double precision          as severity,
    evidence::jsonb                     as evidence,
    source_record_url::text             as source_record_url,
    anomaly_score::double precision     as anomaly_score,
    anomaly_any::boolean                as anomaly_any
from deduped
