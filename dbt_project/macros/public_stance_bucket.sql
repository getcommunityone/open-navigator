{#-
    Public-comment stance bucket (for / against / question / neutral) from the extraction's `stance` text.

    The prompts (prompts/policy_analysis_part_1.md, policy_analysis_lite.md) ask for
    exactly: For, Against, Asked questions, Mixed or neutral, Not stated. Older or off-vocabulary
    values (support / oppose / neutral ...) are mapped where the meaning is plain.
      for      = the speaker asked the body to take the action
      against  = the speaker asked the body not to
      question = the speaker only asked questions or sought information
      neutral  = mixed, conditional, information only, or no stated side
      null     = no stance value, or one outside the vocabulary (unknown is not neutral)
    Case, surrounding spaces and a trailing full stop are ignored.
    Design: web_docs/docs/development/meeting-sentiment-design.md
-#}
{% macro public_stance_bucket(expr) -%}
{%- set v -%} lower(btrim({{ expr }}, E' \t\n.!')) {%- endset -%}
case
    when {{ expr }} is null then null
    when {{ v }} in ('for', 'support', 'supports', 'supportive', 'in favor', 'pro') then 'for'
    when {{ v }} in ('against', 'oppose', 'opposes', 'opposed', 'opposition', 'con') then 'against'
    when {{ v }} in ('asked questions', 'asked question', 'question', 'questions') then 'question'
    when {{ v }} in ('mixed or neutral', 'mixed', 'neutral', 'conditional', 'not stated') then 'neutral'
    else null
end
{%- endmacro %}
