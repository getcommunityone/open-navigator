{{
    config(
        materialized='table',
        tags=['intermediate', 'civic', 'interestingness']
    )
}}

/*
int_civic__item_signal_norms — each interestingness component normalized to [0,1].

Per the spec, UNBOUNDED metrics (money, engagement) are normalized with a
PERCENTILE RANK within a peer window — partition = jurisdiction size_tier,
window = trailing `civic_peer_window_days` (default 365) measured from each
item's occurred_at. The percentile is computed as a correlated self-join
(avg of below/equal/above) rather than a fixed-partition percent_rank(), because
the peer set is a true sliding 12-month window, not a static bucket. Money is
log-compressed (ln(1+|x|)) before ranking so a $50K item in a small town still
ranks high against its small-town peers.

ALREADY-BOUNDED, semantically [0,1] signals (conflict ratio, novelty decay,
surprise, urgency) are emitted directly — percentile-ranking an already-meaningful
ratio would distort it.

All component_k are guaranteed in [0,1] and NOT NULL. Degraded/stubbed signals
collapse to 0 (documented), gated by feature-flag vars where a source is missing.
*/

{% set peer_window = var('civic_peer_window_days', 365) %}

with base as (
    select
        *,
        -- engagement metric: speaker count, duration as a sub-unit tiebreak
        public_comment_speaker_count
            + least(coalesce(public_comment_duration_sec, 0) / 86400.0, 0.999) as engagement_metric
    from {{ ref('int_civic__item_signals') }}
),

-- trailing-window percentile within size_tier (sliding 12-month peer set)
percentiles as (
    select
        s.event_decision_id,
        avg(case
                when p.money_metric < s.money_metric then 1.0
                when p.money_metric = s.money_metric then 0.5
                else 0.0
            end) as money_pct,
        avg(case
                when p.engagement_metric < s.engagement_metric then 1.0
                when p.engagement_metric = s.engagement_metric then 0.5
                else 0.0
            end) as engagement_pct
    from base s
    join base p
      on p.size_tier = s.size_tier
     and p.occurred_at between s.occurred_at - {{ peer_window }} and s.occurred_at
    group by s.event_decision_id
),

components as (
    select
        b.event_decision_id,

        -- raw percentiles (kept for buried + explainability)
        coalesce(pc.money_pct, 0.0)       as money_pct,
        coalesce(pc.engagement_pct, 0.0)  as engagement_pct,

        ---------------------------------------------------------------
        -- conflict: vote closeness, blended with competing-views; falls
        -- back to competing-views presence when there is no recorded vote
        -- (the spec's debate-length fallback has no source today).
        ---------------------------------------------------------------
        case
            when b.total_votes > 0 then least(1.0,
                0.7 * (1 - abs(coalesce(b.votes_yes,0) - coalesce(b.votes_no,0))::numeric
                           / nullif(b.total_votes, 0))
                + 0.3 * (case when b.has_competing_views then 1 else 0 end)
            )
            when b.has_competing_views then least(1.0, 0.5 + 0.1 * least(b.competing_views_count, 5))
            when b.debate_duration_sec is not null then 0.0  -- debate-pct fallback (no source -> 0)
            else 0.0
        end                                as conflict,

        ---------------------------------------------------------------
        -- money: percentile of log money, + fee/tax bonus (feature-flagged,
        -- no source today). Zero-money items score 0, not a tie-percentile.
        ---------------------------------------------------------------
        least(1.0,
            case when b.net_dollar_impact > 0 then coalesce(pc.money_pct, 0.0) else 0.0 end
            {% if var('civic_enable_fee_tax_bonus', false) %}
            + case when b.is_new_or_increased_fee_tax then {{ var('civic_fee_tax_bonus', 0.15) }} else 0.0 end
            {% endif %}
        )                                  as money,

        -- novelty: 1.0 on first appearance of subject for this body, decaying
        -- harmonically with prior occurrences (1/appearance_idx).
        1.0 / b.appearance_idx             as novelty,

        -- engagement: percentile of public-comment speakers; 0 when none spoke.
        case when b.public_comment_speaker_count > 0 then coalesce(pc.engagement_pct, 0.0) else 0.0 end
                                           as engagement,

        -- surprise: outcome reversal vs a prior session on same subject = 1.0;
        -- a mere revisit (no flip) = 0.5; first appearance = 0.
        case
            when b.is_reversal then 1.0
            when b.is_revisit  then 0.5
            else 0.0
        end                                as surprise,

        -- urgency: forward items only -> max(0, 1 - days_until/horizon). No
        -- upcoming-agenda source exists today, so scheduled_for is always NULL
        -- and this is 0 for every row (the `soon` lens is empty until a source
        -- lands). Computed, not faked.
        case
            when b.scheduled_for is not null then
                greatest(0.0, 1.0 - (b.scheduled_for - current_date)::numeric
                                    / {{ var('civic_urgency_horizon_days', 14) }})
            else 0.0
        end                                as urgency,

        -- buried: high-impact item that drew (near-)zero discussion. Needs a
        -- discussion signal (consent-agenda flag or debate length) that has no
        -- source yet; we use public-comment engagement as the only available
        -- discussion proxy, and otherwise leave buried = 0 rather than flag every
        -- high-money item as buried. Wire is_consent_agenda here when it lands.
        case
            when b.net_dollar_impact > 0 and b.public_comment_speaker_count > 0
                then coalesce(pc.money_pct, 0.0) * (1 - coalesce(pc.engagement_pct, 0.0))
            {% if var('civic_enable_buried_no_discussion', false) %}
            when b.net_dollar_impact > 0
                then coalesce(pc.money_pct, 0.0)
            {% endif %}
            else 0.0
        end                                as buried

    from base b
    left join percentiles pc on pc.event_decision_id = b.event_decision_id
)

select
    event_decision_id,
    money_pct,
    engagement_pct,
    -- clamp every component to [0,1] defensively
    least(1.0, greatest(0.0, conflict))   as conflict,
    least(1.0, greatest(0.0, money))      as money,
    least(1.0, greatest(0.0, novelty))    as novelty,
    least(1.0, greatest(0.0, engagement)) as engagement,
    least(1.0, greatest(0.0, surprise))   as surprise,
    least(1.0, greatest(0.0, urgency))    as urgency,
    least(1.0, greatest(0.0, buried))     as buried
from components
