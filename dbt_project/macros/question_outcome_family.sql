{#-
    Outcome family of a policy-question instance (#499). One rule shared by
    int_policy_question_rollup (the counts) and question_instance (the column the
    API filters and counts by state/city), so a scoped count can never drift from
    the national rollup. Unifies the decision and bill vocabularies:
      moratorium = moratorium (decisions: an adopted/recommended moratorium, #483)
      approved   = approved (decisions) | enacted (bills)
      denied     = denied (decisions) | failed | died_in_committee (bills)
      deferred   = deferred (decisions) | carried_over (bills)
      other      = everything else (other, pending, null)
-#}
{% macro question_outcome_family(col) -%}
case
    when {{ col }} = 'moratorium' then 'moratorium'
    when {{ col }} in ('approved', 'enacted') then 'approved'
    when {{ col }} in ('denied', 'failed', 'died_in_committee') then 'denied'
    when {{ col }} in ('deferred', 'carried_over') then 'deferred'
    else 'other'
end
{%- endmacro %}
