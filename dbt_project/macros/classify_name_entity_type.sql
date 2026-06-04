{% macro classify_name_entity_type(name_col) -%}
    /*
        Heuristic person-vs-organization tag from a raw name string. Parcel
        owner_name and campaign contributor_name both mix individuals with
        businesses / committees / government bodies; this keeps them in separate
        match pools (Splink blocks within entity_type) so a person never links to
        an LLC. Defaults to 'person'. Word-boundary matched to avoid clobbering
        surnames (e.g. 'inc' won't fire inside 'Vince').

        Token choice is data-driven against mdm_person: tokens here must be
        org-only words that are effectively never standalone surnames. That is why
        'council' and 'league' are deliberately EXCLUDED (real people: "Nancy
        Council", "Bob League") while 'group', 'institute', 'associates',
        'services', etc. ARE included — firm/PAC/committee names like "Elias Law
        Group" and "World Resources Institute" were otherwise defaulting to
        'person' and leaking into People search.
        See web_docs/docs/dbt/entity-resolution-mdm.md (Watch-outs: orgs vs people).
    */
CASE
    WHEN {{ name_col }} IS NULL THEN 'person'
    WHEN lower({{ name_col }}) ~
        '\y(llc|inc|incorporated|corp|corporation|company|ltd|lp|llp|pllc|trust|foundation|fund|association|assn|committee|pac|church|ministry|ministries|board|district|department|authority|university|college|academy|institute|society|bank|properties|partners|holdings|enterprises|estate|county|township|village|group|associates|services|systems|solutions|technologies|industries|coalition|alliance|federation|network)\y'
        or lower({{ name_col }}) ~ '\y(city|town|state) of\y'
        then 'organization'
    ELSE 'person'
END
{%- endmacro %}
