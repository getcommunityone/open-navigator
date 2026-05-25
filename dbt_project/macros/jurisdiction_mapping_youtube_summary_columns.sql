{% macro jurisdiction_mapping_youtube_summary_columns() %}
    COUNT(*) FILTER (WHERE COALESCE(has_youtube_channel, FALSE))::BIGINT AS with_youtube_channel,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE COALESCE(has_youtube_channel, FALSE))::NUMERIC
        / NULLIF(COUNT(*)::NUMERIC, 0),
        2
    ) AS pct_with_youtube_channel
{% endmacro %}
