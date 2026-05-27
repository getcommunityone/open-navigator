{% macro latest_per_natural_key(relation, partition_by, order_by) %}
{#-
    Keep only the latest row per natural key.
    Returns a SELECT (use inside a CTE): the row with the greatest `order_by`
    per `partition_by` group. Adds no columns to the caller's projection
    except a transient `_latest_rn` (project explicit columns downstream).
-#}
    select * from (
        select
            *,
            row_number() over (
                partition by {{ partition_by }}
                order by {{ order_by }} desc nulls last
            ) as _latest_rn
        from {{ relation }}
    ) _ranked
    where _latest_rn = 1
{% endmacro %}
