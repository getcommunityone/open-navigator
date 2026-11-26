{% snapshot officials_roster_snapshot %}
{#-
    Local officials' roster over time (#1068). Each run records a change to a seat, title, district or whether the
    official is still current, with dbt_valid_from / dbt_valid_to = when we first and last saw that version. These are
    observation dates, not term dates: person_government_term exposes them as first_seen_on / last_seen_on, never as a
    term start or end. Someone dropped from the roster gets dbt_valid_to set (hard deletes invalidated).
-#}
{{
    config(
        target_schema='snapshots',
        unique_key='id',
        strategy='check',
        check_cols=['title', 'district', 'jurisdiction', 'is_current'],
        invalidate_hard_deletes=True,
    )
}}
select id, full_name, title, jurisdiction, state_code, district, office, is_current,
       current_timestamp as last_updated  -- the run time: when this version was seen (the project's snapshot updated_at)
from {{ ref('contact_official') }}
where office in ('government', 'executive')
{% endsnapshot %}
