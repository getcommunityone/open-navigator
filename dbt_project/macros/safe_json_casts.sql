{#-
    Guarded casts for values an LLM wrote into JSON (DC-1.1, #246). The model sometimes
    emits strings for numbers ("about 500", "1,200") or free-text dates ("spring 2027").
    Each macro returns the typed value when the text is clean, otherwise NULL. Never a
    default or a guess.

    Nested CASEs (not AND) so Postgres only reaches a cast after the guard passed.
-#}

{% macro safe_iso_date(expr) -%}
(
    case
        when ({{ expr }}) ~ '^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
        then case
            -- reject impossible days (2026-02-30): compare with the month's last day
            when substring(({{ expr }}) from 9 for 2)::integer <= extract(day from (
                    make_date(
                        substring(({{ expr }}) from 1 for 4)::integer,
                        substring(({{ expr }}) from 6 for 2)::integer,
                        1
                    ) + interval '1 month - 1 day'
                 ))::integer
            then ({{ expr }})::date
        end
    end
)
{%- endmacro %}

{% macro safe_nonnegative_integer(expr) -%}
(
    case
        -- strip thousands separators and whitespace; allow a trailing ".0" (JSON 500.0);
        -- at most 9 digits so the cast can't overflow integer
        when regexp_replace(({{ expr }}), '[\s,]', '', 'g') ~ '^[0-9]{1,9}(\.0+)?$'
        then regexp_replace(({{ expr }}), '[\s,]', '', 'g')::numeric::integer
    end
)
{%- endmacro %}

{% macro safe_nonnegative_double(expr) -%}
(
    case
        when btrim({{ expr }}) ~ '^[0-9]{1,12}(\.[0-9]+)?$'
        then btrim({{ expr }})::double precision
    end
)
{%- endmacro %}
