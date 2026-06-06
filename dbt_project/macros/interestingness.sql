/*
Helpers for the civic interestingness score.

  * civic_component_weights()      -> a one-row CTE body that pivots the
                                      interestingness_weights seed to one column
                                      per component (so weights are tunable via the
                                      seed, never hardcoded in a model).
  * civic_outcome_polarity(expr)   -> +1 / 0 / -1 sign for a decision `outcome`
                                      string, used by the `surprise` (reversal)
                                      component.
  * rank_for_user(...)             -> serving-layer query: ranks
                                      public.item_interestingness for one lens +
                                      user location, applying the lens eligibility
                                      filter, time window, and a PER-REQUEST
                                      proximity boost (proximity never lives in the
                                      static score). See analyses/ for usage.

Keep the component list here in sync with seeds/interestingness_weights.csv and
the component columns emitted by item_interestingness.
*/

{% macro civic_component_weights() -%}
select
    max(case when component = 'conflict'   then weight else 0 end) as w_conflict,
    max(case when component = 'money'      then weight else 0 end) as w_money,
    max(case when component = 'novelty'    then weight else 0 end) as w_novelty,
    max(case when component = 'engagement' then weight else 0 end) as w_engagement,
    max(case when component = 'surprise'   then weight else 0 end) as w_surprise,
    max(case when component = 'urgency'    then weight else 0 end) as w_urgency,
    max(case when component = 'buried'     then weight else 0 end) as w_buried,
    nullif(sum(weight), 0)                                         as w_total
from {{ ref('interestingness_weights') }}
{%- endmacro %}


{% macro civic_outcome_polarity(expr) -%}
case
    when {{ expr }} is null then 0
    when lower({{ expr }}) ~ '(approv|adopt|pass|authoriz|award|grant|ratif|confirm|accept)'
        and lower({{ expr }}) !~ 'recommend' then 1
    when lower({{ expr }}) ~ '(den(y|ied)|reject|fail|defeat|table|defer|continu|withdraw|postpon)' then -1
    else 0
end
{%- endmacro %}


{#-
  rank_for_user — serving-layer ranked feed for ONE lens and ONE user location.

  Reads item_interestingness, joins the lens_config seed row for `lens_id`
  (fetched at COMPILE time via run_query so the eligibility_sql / sort_expr land
  inline), applies:
    * the lens eligibility filter,
    * a time window: occurred_at >= now - window_days for past lenses; for the
      forward-looking `soon` lens, scheduled_for <= now + window_days,
    * a per-request Haversine proximity boost vs (user_lat, user_lng) within
      civic_proximity_radius_m (proximity is the ONLY per-request signal and is
      deliberately absent from the static score),
  then orders by the lens's sort_expr (default feed -> interestingness_score).

  Invoke with literal args (it resolves the lens row at compile), e.g. from an
  analysis or a per-request dbt compile. user_lat/user_lng may be 'null' to skip
  the proximity boost (then proximity_meters is null and sorts last).
-#}
{% macro rank_for_user(lens_id, user_lat='null', user_lng='null', window_days=365, limit_n=100) %}
{%- set radius_m = var('civic_proximity_radius_m', 40000) -%}
{%- set lens_row = {'eligibility_sql': 'true', 'sort_expr': 'interestingness_score', 'direction': 'desc'} -%}
{%- if execute -%}
  {%- set q -%}
    select eligibility_sql, sort_expr, direction
    from {{ ref('lens_config') }}
    where lens_id = '{{ lens_id }}'
  {%- endset -%}
  {%- set res = run_query(q) -%}
  {%- if res and res.rows | length > 0 -%}
    {%- set lens_row = {'eligibility_sql': res.rows[0][0], 'sort_expr': res.rows[0][1], 'direction': res.rows[0][2]} -%}
  {%- endif -%}
{%- endif -%}

-- depends_on: {{ ref('lens_config') }}
-- depends_on: {{ ref('item_interestingness') }}
with feed as (
    select
        f.*,
        case
            when {{ user_lat }}::float is null or f.primary_latitude is null then null
            else 2 * 6371000 * asin(sqrt(
                power(sin(radians(f.primary_latitude - {{ user_lat }}::float) / 2), 2)
                + cos(radians({{ user_lat }}::float)) * cos(radians(f.primary_latitude))
                * power(sin(radians(f.primary_longitude - {{ user_lng }}::float) / 2), 2)
            ))
        end as proximity_meters
    from {{ ref('item_interestingness') }} f
),

eligible as (
    select
        *,
        -- proximity boost ∈ [0,1]: 1 at the user, 0 at/after the radius edge
        case
            when proximity_meters is null then 0.0
            else greatest(0.0, 1.0 - proximity_meters / {{ radius_m }}.0)
        end as proximity_boost
    from feed
    where ({{ lens_row['eligibility_sql'] }})
      {% if lens_id == 'soon' -%}
      and scheduled_for is not null
      and scheduled_for <= current_date + {{ window_days }}
      {%- else -%}
      and occurred_at >= current_date - {{ window_days }}
      {%- endif %}
)

select
    *,
    -- final per-request rank value: lens sort signal lifted by proximity.
    interestingness_score * (1 + proximity_boost) as feed_rank_value
from eligible
order by {{ lens_row['sort_expr'] }} {{ lens_row['direction'] }} nulls last,
         proximity_boost desc,
         interestingness_score desc
limit {{ limit_n }}
{% endmacro %}
