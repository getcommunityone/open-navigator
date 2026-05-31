{% macro classify_name_entity_type(name_col) -%}
    /*
        Heuristic person-vs-organization tag from a raw name string. Parcel
        owner_name and campaign contributor_name both mix individuals with
        businesses / committees / government bodies; this keeps them in separate
        match pools (Splink blocks within entity_type) so a person never links to
        an LLC. Defaults to 'person'. Word-boundary matched to avoid clobbering
        surnames (e.g. 'inc' won't fire inside 'Vince').
        See web_docs/docs/dbt/entity-resolution-mdm.md (Watch-outs: orgs vs people).
    */
CASE
    WHEN {{ name_col }} IS NULL THEN 'person'
    WHEN lower({{ name_col }}) ~
        '\y(llc|inc|incorporated|corp|corporation|company|ltd|lp|llp|pllc|trust|foundation|fund|association|assn|committee|pac|church|ministries|board|district|department|authority|university|college|bank|properties|partners|holdings|enterprises|estate|county|township|village|authority)\y'
        or lower({{ name_col }}) ~ '\y(city|town|state) of\y'
        then 'organization'
    ELSE 'person'
END
{%- endmacro %}
