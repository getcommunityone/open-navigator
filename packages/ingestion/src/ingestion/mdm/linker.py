"""Run Splink against a conformed MDM pool and write entity clusters back.

Pipeline per entity (web_docs/docs/dbt/entity-resolution-mdm.md, Layer 3→4):
    1. pick the conformed input table + Splink settings
    2. estimate u (random sampling) + m (expectation maximisation)
    3. predict pairwise matches above a probability threshold
    4. cluster the predictions -> one master id per occurrence
    5. write bronze.entity_<entity>_clusters for dbt to serve (Layer 5)

Entity types are kept in separate pools: the person run resolves only
entity_type='person' rows (org-shaped names feed a future organization pool), so
a person never links to an LLC.

This module does the heavy compute; survivorship / golden-record selection stays
in dbt downstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from ingestion.mdm.db import get_engine
from ingestion.mdm.settings import address_settings, location_settings, person_settings


@dataclass(frozen=True)
class EntitySpec:
    name: str
    source_table: str           # conformed input (schema-qualified)
    unique_id: str              # Splink unique_id_column_name
    settings_factory: callable
    output_table: str           # where clusters land (schema-qualified)
    input_filter: str | None = None  # SQL predicate to restrict the input pool
    # EM training blocks — multi-column so training pairs stay bounded.
    em_blocking: tuple[tuple[str, ...], ...] = ()
    # Where the pairwise candidate edges land (schema-qualified). The 0.9–0.99 band
    # (predicted but not auto-merged) is the ambiguous-match review queue. None ->
    # don't persist edges (e.g. the deterministic-leaning address pool).
    predictions_table: str | None = None


# source_table is a BARE name (resolved via the engine search_path) — the Splink
# Postgres backend does not accept schema-qualified input names.
SPECS: dict[str, EntitySpec] = {
    "address": EntitySpec(
        name="address",
        source_table="int_addresses__unioned",
        unique_id="address_uid",
        settings_factory=address_settings,
        output_table="bronze.entity_address_clusters",
        em_blocking=(("zip5", "street_name"), ("zip5", "street_number")),
    ),
    "person": EntitySpec(
        name="person",
        source_table="int_persons__unioned",
        unique_id="person_uid",
        settings_factory=person_settings,
        output_table="bronze.entity_person_clusters",
        predictions_table="bronze.entity_person_predictions",
        input_filter="entity_type = 'person' and is_probable_person",
        # EM is iterative, so its training blocks are tighter than the prediction
        # blocks (adding state_code shrinks training pairs ~30-50x) — parameter
        # estimates barely change, but EM runs in ~1 min instead of ~20.
        em_blocking=(
            ("name_phonetic_last", "name_phonetic_first", "state_code"),
            ("family_name_norm", "state_code"),
        ),
    ),
    "location": EntitySpec(
        name="location",
        source_table="mdm_location_input",
        unique_id="location_uid",
        settings_factory=location_settings,
        output_table="bronze.entity_location_clusters",
        predictions_table="bronze.entity_location_predictions",
        em_blocking=(
            ("state_code", "name_initial", "city_norm"),
            ("state_code", "domain"),
        ),
    ),
}


def _prepare_location_input(engine) -> str:
    """Build a conformed location pool for cross-source linkage.

    Input sources mirror the MDM source set used by dbt:
      - public.organization_location
      - public.jurisdictions_wikidata
      - public.jurisdiction
    """
    sql = """
    create or replace view bronze.mdm_location_input as
    with
    org as (
        select
            'organization_location'::varchar as source_system,
            id::varchar as source_pk,
            nullif(trim(source_id), '') as source_id,
            nullif(trim(name), '') as raw_name,
            nullif(trim(city), '') as raw_city,
            upper(nullif(trim(state), '')) as state_code,
            nullif(trim(county), '') as raw_county,
            nullif(trim(website), '') as website_url,
            nullif(regexp_replace(coalesce(telephone, ''), '[^0-9]', '', 'g'), '') as phone_digits,
            null::varchar as zip5,
            latitude::double precision as lat,
            longitude::double precision as lon
        from public.organization_location
    ),
    wiki as (
        select
            'jurisdictions_wikidata'::varchar as source_system,
            id::varchar as source_pk,
            nullif(trim(nces_id), '') as source_id,
            nullif(trim(jurisdiction_name), '') as raw_name,
            null::varchar as raw_city,
            upper(nullif(trim(state_code), '')) as state_code,
            null::varchar as raw_county,
            nullif(trim(official_website), '') as website_url,
            null::varchar as phone_digits,
            null::varchar as zip5,
            latitude::double precision as lat,
            longitude::double precision as lon
        from public.jurisdictions_wikidata
    ),
    jur as (
        select
            'jurisdiction'::varchar as source_system,
            id::varchar as source_pk,
            nullif(trim(geoid), '') as source_id,
            nullif(trim(name), '') as raw_name,
            nullif(trim(name), '') as raw_city,
            upper(nullif(trim(state_code), '')) as state_code,
            nullif(trim(county), '') as raw_county,
            nullif(trim(website_url), '') as website_url,
            null::varchar as phone_digits,
            null::varchar as zip5,
            null::double precision as lat,
            null::double precision as lon
        from public.jurisdiction
    ),
    unioned as (
        select * from org
        union all
        select * from wiki
        union all
        select * from jur
    ),
    normalized as (
        select
            source_system || ':' || source_pk as location_uid,
            source_system,
            source_pk,
            source_id,
            raw_name,
            raw_city,
            raw_county,
            state_code,
            website_url,
            phone_digits,
            nullif(substr(regexp_replace(coalesce(zip5, ''), '[^0-9]', '', 'g'), 1, 5), '') as zip5,
            lat,
            lon,
            nullif(
                lower(trim(regexp_replace(coalesce(raw_name, ''), '[^a-z0-9 ]', '', 'g'))),
                ''
            ) as name_norm,
            nullif(
                lower(trim(regexp_replace(coalesce(raw_city, ''), '[^a-z0-9 ]', '', 'g'))),
                ''
            ) as city_norm,
            nullif(
                lower(trim(regexp_replace(coalesce(raw_county, ''), '[^a-z0-9 ]', '', 'g'))),
                ''
            ) as county_norm,
            nullif(
                lower(trim(substring(regexp_replace(coalesce(raw_name, ''), '[^a-z0-9 ]', '', 'g') from 1 for 1))),
                ''
            ) as name_initial,
            case
                when website_url is null then null
                when website_url ilike '%not available%' then null
                else nullif(
                    lower(trim(
                        regexp_replace(
                            regexp_replace(website_url, '^https?://(www\\.)?', '', 'i'),
                            '/.*$', ''
                        )
                    )),
                    ''
                )
            end as domain
        from unioned
    )
    select
        location_uid,
        source_system,
        source_pk,
        source_id,
        raw_name,
        raw_city,
        raw_county,
        state_code,
        website_url,
        domain,
        phone_digits,
        zip5,
        lat,
        lon,
        name_norm,
        city_norm,
        county_norm,
        name_initial
    from normalized
    where name_norm is not null
      and state_code is not null
    """
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info("Prepared location input view bronze.mdm_location_input")
    return "mdm_location_input"


def _materialize_location_outputs(engine, *, match_threshold: float, cluster_threshold: float) -> None:
    """Build location serving + review outputs after Splink clustering."""
    with engine.begin() as conn:
        conn.execute(text("""
            create or replace table bronze.unified_location as
            with linked as (
                select
                    c.master_location_id,
                    i.location_uid,
                    i.source_system,
                    i.source_pk,
                    i.source_id,
                    i.raw_name,
                    i.raw_city,
                    i.raw_county,
                    i.state_code,
                    i.website_url,
                    i.domain,
                    i.phone_digits,
                    i.zip5,
                    i.lat,
                    i.lon,
                    row_number() over (
                        partition by c.master_location_id
                        order by
                            case i.source_system
                                when 'organization_location' then 1
                                when 'jurisdiction' then 2
                                when 'jurisdictions_wikidata' then 3
                                else 9
                            end,
                            case when i.website_url is not null then 0 else 1 end,
                            case when i.lat is not null and i.lon is not null then 0 else 1 end,
                            length(coalesce(i.raw_name, '')) desc
                    ) as pick_rank
                from bronze.entity_location_clusters c
                join bronze.mdm_location_input i
                    on i.location_uid = c.location_uid
            ),
            cluster_agg as (
                select
                    master_location_id,
                    count(*) as cluster_size,
                    count(distinct source_system) as source_count,
                    string_agg(distinct source_system, ', ' order by source_system) as source_systems,
                    min(website_url) filter (where website_url is not null) as fallback_website_url,
                    min(domain) filter (where domain is not null) as fallback_domain
                from linked
                group by master_location_id
            ),
            canonical as (
                select *
                from linked
                where pick_rank = 1
            )
            select
                c.master_location_id,
                c.location_uid as canonical_location_uid,
                c.source_system as canonical_source_system,
                c.source_pk as canonical_source_pk,
                c.source_id as canonical_source_id,
                c.raw_name as location_name,
                c.raw_city as city,
                c.raw_county as county,
                c.state_code,
                c.phone_digits,
                c.zip5,
                c.lat as latitude,
                c.lon as longitude,
                coalesce(c.website_url, a.fallback_website_url) as website_url,
                coalesce(c.domain, a.fallback_domain) as domain,
                case
                    when c.website_url is not null then 'canonical_row'
                    when a.fallback_website_url is not null then 'cluster_imputed'
                    else 'missing'
                end as website_resolution,
                a.cluster_size,
                a.source_count,
                a.source_systems,
                current_timestamp as updated_at
            from canonical c
            join cluster_agg a
                on a.master_location_id = c.master_location_id
        """))

        conn.execute(text("""
            create or replace table bronze.location_review_flags as
            with cluster_map as (
                select
                    location_uid,
                    master_location_id
                from bronze.entity_location_clusters
            ),
            edge_flags as (
                select
                    'suspected_duplicate'::varchar as flag_type,
                    coalesce(cm_l.master_location_id, cm_r.master_location_id) as master_location_id,
                    p.location_uid_l,
                    p.location_uid_r,
                    p.match_probability as score,
                    case
                        when cm_l.master_location_id is distinct from cm_r.master_location_id
                            then 'high-probability pair fell into different clusters'
                        else 'borderline pair in same cluster; needs manual verification'
                    end as reason,
                    'review_merge'::varchar as recommended_action
                from bronze.entity_location_predictions p
                left join cluster_map cm_l
                    on cm_l.location_uid = p.location_uid_l
                left join cluster_map cm_r
                    on cm_r.location_uid = p.location_uid_r
                where p.match_probability >= :match_threshold
                  and p.match_probability < :cluster_threshold
            ),
            domain_split as (
                select
                    'suspected_duplicate'::varchar as flag_type,
                    min(c.master_location_id) as master_location_id,
                    null::varchar as location_uid_l,
                    null::varchar as location_uid_r,
                    0.99::double precision as score,
                    'same domain appears in multiple clusters: ' || u.domain as reason,
                    'review_merge'::varchar as recommended_action
                from bronze.unified_location u
                join bronze.entity_location_clusters c
                    on c.master_location_id = u.master_location_id
                where u.domain is not null
                group by u.domain
                having count(distinct u.master_location_id) > 1
            ),
            missing_website as (
                select
                    'missing_website'::varchar as flag_type,
                    u.master_location_id,
                    null::varchar as location_uid_l,
                    null::varchar as location_uid_r,
                    null::double precision as score,
                    'no website_url found in any linked source row' as reason,
                    'add_website'::varchar as recommended_action
                from bronze.unified_location u
                where u.website_url is null
            ),
            source_gap as (
                select
                    'missing_from_other_sources'::varchar as flag_type,
                    u.master_location_id,
                    null::varchar as location_uid_l,
                    null::varchar as location_uid_r,
                    null::double precision as score,
                    'record appears in one source only; look for counterpart rows in other source feeds' as reason,
                    'review_add_source_record'::varchar as recommended_action
                from bronze.unified_location u
                where u.source_count = 1
            ),
            unioned as (
                select * from edge_flags
                union all
                select * from domain_split
                union all
                select * from missing_website
                union all
                select * from source_gap
            )
            select
                row_number() over (order by flag_type, coalesce(score, 0.0) desc, master_location_id) as review_flag_id,
                flag_type,
                master_location_id,
                location_uid_l,
                location_uid_r,
                score,
                reason,
                recommended_action,
                current_timestamp as created_at
            from unioned
        """), {"match_threshold": match_threshold, "cluster_threshold": cluster_threshold})

    logger.success("Built bronze.unified_location and bronze.location_review_flags")


def _prepare_input(engine, spec: EntitySpec) -> str:
    """Return the table/view name Splink should read.

    For a filtered pool (person), materialise a view so Splink sees only the
    relevant entity_type without us mutating the source.
    """
    if spec.name == "location":
        return _prepare_location_input(engine)

    if spec.input_filter is None:
        return spec.source_table
    bare = f"mdm_{spec.name}_input"
    with engine.begin() as conn:
        conn.execute(text(
            f"create or replace view bronze.{bare} as "
            f"select * from {spec.source_table} "
            f"where {spec.input_filter}"
        ))
    logger.info("Prepared filtered input view bronze.{} (where {})", bare, spec.input_filter)
    return bare  # bare name; resolved via search_path


def run_linker(
    entity: str,
    *,
    match_threshold: float = 0.9,
    cluster_threshold: float = 0.99,
    train_max_pairs: float = 1e7,
    dry_run: bool = False,
) -> str:
    """Resolve one entity pool end to end. Returns the output table name.

    match_threshold gates which pairs are predicted (candidate edges);
    cluster_threshold (stricter) gates which edges actually merge records. Keeping
    clustering stricter than prediction limits single-linkage chaining — at equal
    thresholds a dense block can fuse unrelated records into one mega-cluster.

    dry_run builds the linker + settings and stops before any estimation, so the
    configuration can be validated without the (multi-hour) compute.
    """
    if entity not in SPECS:
        raise ValueError(f"unknown entity {entity!r}; choose from {sorted(SPECS)}")
    spec = SPECS[entity]

    # Imported lazily so the package imports without splink installed.
    from splink import Linker
    from splink.backends.postgres import PostgresAPI

    engine = get_engine()
    input_name = _prepare_input(engine, spec)
    settings = spec.settings_factory()

    # Splink writes its working tables to the `splink` schema and SETs search_path
    # to it, which overrides the engine-level path — so the input schemas must be
    # declared to Splink directly via other_schemas_to_search (not just the engine).
    db_api = PostgresAPI(
        engine=engine,
        schema="splink",
        other_schemas_to_search=["intermediate", "bronze", "public"],
    )
    linker = Linker(input_name, settings, db_api=db_api)
    logger.info("Linker built for {} on {}", entity, input_name)

    if dry_run:
        logger.success("Dry run OK — settings + linker valid for {}", entity)
        return spec.output_table

    logger.info("Estimating u via random sampling (max_pairs={:.0e}) …", train_max_pairs)
    linker.training.estimate_u_using_random_sampling(max_pairs=train_max_pairs)

    # EM on the entity's multi-column training blocks (bounded pair counts).
    from splink import block_on
    for cols in spec.em_blocking:
        try:
            linker.training.estimate_parameters_using_expectation_maximisation(block_on(*cols))
        except Exception as err:  # noqa: BLE001 — EM on a sparse rule may give up; keep going
            logger.warning("EM skipped for block_on{}: {}", cols, err)

    logger.info("Predicting pairwise matches (threshold={}) …", match_threshold)
    predictions = linker.inference.predict(threshold_match_probability=match_threshold)

    logger.info("Clustering predictions (threshold={}) …", cluster_threshold)
    clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
        predictions, threshold_match_probability=cluster_threshold
    )

    df = clusters.as_pandas_dataframe()
    keep = [c for c in ("cluster_id", spec.unique_id, "source_system", "source_pk") if c in df.columns]
    df = df[keep].rename(columns={"cluster_id": f"master_{spec.name}_id"})

    # Retain Splink confidence (when the spec opts in). Two artefacts:
    #   1. the raw candidate edges (predictions_table) — the review queue, including
    #      the 0.9–0.99 band that was predicted but not auto-merged at cluster_threshold;
    #   2. a per-node match_confidence on the cluster rows = the strongest incident
    #      edge probability for that occurrence. A merged node sits at >= cluster_threshold;
    #      a node whose only link is a borderline candidate sits in [match,cluster); a
    #      node with no candidate at all is NULL (isolated — no merge to be confident about).
    if spec.predictions_table:
        import pandas as pd  # local import: keeps the package importable without pandas/splink

        uid = spec.unique_id
        preds = predictions.as_pandas_dataframe()
        edge_cols = [c for c in (f"{uid}_l", f"{uid}_r", "match_probability", "match_weight") if c in preds.columns]
        edges = preds[edge_cols].copy()

        pred_schema, pred_name = spec.predictions_table.split(".", 1)
        edges.to_sql(
            pred_name, engine, schema=pred_schema,
            if_exists="replace", index=False, chunksize=10_000,
        )
        logger.success("Wrote {:,} candidate edge rows to {}", len(edges), spec.predictions_table)

        incident = pd.concat([
            edges[[f"{uid}_l", "match_probability"]].rename(columns={f"{uid}_l": uid}),
            edges[[f"{uid}_r", "match_probability"]].rename(columns={f"{uid}_r": uid}),
        ])
        node_conf = (
            incident.groupby(uid)["match_probability"].max().rename("match_confidence")
        )
        df = df.merge(node_conf, how="left", left_on=uid, right_index=True)

    df.to_sql(
        spec.output_table.split(".", 1)[1],
        engine,
        schema=spec.output_table.split(".", 1)[0],
        if_exists="replace",
        index=False,
        chunksize=10_000,
    )
    logger.success("Wrote {:,} cluster rows to {}", len(df), spec.output_table)

    if spec.name == "location":
        _materialize_location_outputs(
            engine,
            match_threshold=match_threshold,
            cluster_threshold=cluster_threshold,
        )

    return spec.output_table
