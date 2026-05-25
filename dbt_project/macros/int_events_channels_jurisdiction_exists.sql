{% macro int_events_channels_jurisdiction_exists() %}
  {# Golden county/municipality rows in intermediate.int_events_channels (migration 071). #}
  {% set rel = adapter.get_relation(
      database=target.database,
      schema='intermediate',
      identifier='int_events_channels'
  ) %}
  {% if rel is none %}
    {{ return(false) }}
  {% endif %}
  {% set cols = adapter.get_columns_in_relation(rel) %}
  {% for col in cols %}
    {% if col.name == 'youtube_channel_url' %}
      {{ return(true) }}
    {% endif %}
  {% endfor %}
  {{ return(false) }}
{% endmacro %}
