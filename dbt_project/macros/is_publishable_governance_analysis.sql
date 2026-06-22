{% macro is_publishable_governance_analysis(structured_analysis_col) -%}
  NOT ({{ structured_analysis_col }} ? '_error')
{%- endmacro %}
