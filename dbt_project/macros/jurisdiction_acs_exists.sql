{% macro jurisdiction_acs_exists() %}
  {% set rel = adapter.get_relation(
      database=target.database,
      schema='gold',
      identifier='jurisdiction_acs'
  ) %}
  {{ return(rel is not none) }}
{% endmacro %}
