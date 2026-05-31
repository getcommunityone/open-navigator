{% macro enable_mdm_extensions() %}
    /*
        Enable the Postgres extensions the MDM / entity-resolution pipeline needs:
          - unaccent       : strip diacritics during normalization
          - pg_trgm        : trigram similarity + GIN indexes for name/address search
          - fuzzystrmatch  : dmetaphone / soundex / levenshtein for phonetic keys

        Run once per warehouse:
            dbt run-operation enable_mdm_extensions

        Requires a role with CREATE privilege on the database (superuser on the
        local Postgres). If it fails on permissions, hand this to whoever owns the
        warehouse — the rest of the pipeline assumes these three are present.

        See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 0).
    */
    {% set sql %}
        create extension if not exists unaccent;
        create extension if not exists pg_trgm;
        create extension if not exists fuzzystrmatch;
    {% endset %}
    {% do run_query(sql) %}
    {{ log("MDM extensions ensured: unaccent, pg_trgm, fuzzystrmatch", info=true) }}
{% endmacro %}
