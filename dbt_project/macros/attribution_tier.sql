{% macro attribution_tier(confidence_expr) %}
{#- high >= 0.80, medium >= 0.50, low below (#1386). Same thresholds as the speaker_attribution_rules seed doc. -#}
(case when {{ confidence_expr }} >= 0.80 then 'high' when {{ confidence_expr }} >= 0.50 then 'medium' else 'low' end)
{% endmacro %}
