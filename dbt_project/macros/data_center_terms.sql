{#-
    Data center words for transcript matching (#445), shared by
    stg_event_youtube_transcript__data_center, int_data_center_transcript__passage and
    data_center_meeting_mention so the prefilter, the passage filter and the highlight
    always mean the same thing.

    data_center_index_tsquery: loose (no phrase operator) so the GIN index on
        to_tsvector('english', coalesce(raw_text, '')) answers it without a heap recheck.
    data_center_regex: the exact test, with word boundaries ("metadata center" is no hit).
    data_center_headline_tsquery: what ts_headline marks in the evidence.
-#}

{% macro data_center_index_tsquery() -%}
to_tsquery('english', '(data & center) | (data & centre) | datacenter | datacentre | hyperscale | hyperscaler')
{%- endmacro %}

{% macro data_center_regex() -%}
\y(data[ -]?cent(er|re)s?|datacent(er|re)s?|hyperscal(e|er|ers)?)\y
{%- endmacro %}

{% macro data_center_headline_tsquery() -%}
to_tsquery('english', '(data <-> center) | (data <-> centre) | datacenter | datacentre | hyperscale | hyperscaler')
{%- endmacro %}
