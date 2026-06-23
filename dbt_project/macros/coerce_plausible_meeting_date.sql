{% macro coerce_plausible_meeting_date(meeting_date_expr, meeting_id_expr) %}
(
    case
        when {{ meeting_date_expr }} ~ '^\d{4}-\d{2}-\d{2}$'
             and substring({{ meeting_date_expr }} from 1 for 4)::integer between 1990 and 2035
        then {{ meeting_date_expr }}
        when substring({{ meeting_id_expr }} from '(\d{4}-\d{2}-\d{2})$') ~ '^\d{4}-\d{2}-\d{2}$'
             and substring(substring({{ meeting_id_expr }} from '(\d{4}-\d{2}-\d{2})$') from 1 for 4)::integer
                 between 1990 and 2035
        then substring({{ meeting_id_expr }} from '(\d{4}-\d{2}-\d{2})$')
        else null
    end
)
{% endmacro %}
