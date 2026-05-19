{% macro jurisdiction_mapping_primary_from_source_columns() %}
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'naco')::BIGINT AS primary_from_naco,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'uscm')::BIGINT AS primary_from_uscm,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'nces_directory')::BIGINT AS primary_from_nces_directory,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'gsa')::BIGINT AS primary_from_gsa,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'league')::BIGINT AS primary_from_league,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'wikidata')::BIGINT AS primary_from_wikidata,
    COUNT(*) FILTER (WHERE has_primary_website AND primary_website_source = 'override')::BIGINT AS primary_from_override
{% endmacro %}
