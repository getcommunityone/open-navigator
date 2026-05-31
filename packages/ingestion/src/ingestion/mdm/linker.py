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
from ingestion.mdm.settings import address_settings, person_settings


@dataclass(frozen=True)
class EntitySpec:
    name: str
    source_table: str           # conformed input (schema-qualified)
    unique_id: str              # Splink unique_id_column_name
    settings_factory: callable
    output_table: str           # where clusters land (schema-qualified)
    entity_type_filter: str | None = None  # restrict the input pool, e.g. 'person'


# source_table is a BARE name (resolved via the engine search_path) — the Splink
# Postgres backend does not accept schema-qualified input names.
SPECS: dict[str, EntitySpec] = {
    "address": EntitySpec(
        name="address",
        source_table="int_addresses__unioned",
        unique_id="address_uid",
        settings_factory=address_settings,
        output_table="bronze.entity_address_clusters",
    ),
    "person": EntitySpec(
        name="person",
        source_table="int_persons__unioned",
        unique_id="person_uid",
        settings_factory=person_settings,
        output_table="bronze.entity_person_clusters",
        entity_type_filter="person",
    ),
}


def _prepare_input(engine, spec: EntitySpec) -> str:
    """Return the table/view name Splink should read.

    For a filtered pool (person), materialise a view so Splink sees only the
    relevant entity_type without us mutating the source.
    """
    if spec.entity_type_filter is None:
        return spec.source_table
    bare = f"mdm_{spec.name}_input"
    with engine.begin() as conn:
        conn.execute(text(
            f"create or replace view bronze.{bare} as "
            f"select * from {spec.source_table} "
            f"where entity_type = :et"
        ), {"et": spec.entity_type_filter})
    logger.info("Prepared filtered input view bronze.{} (entity_type={})", bare, spec.entity_type_filter)
    return bare  # bare name; resolved via search_path


def run_linker(
    entity: str,
    *,
    match_threshold: float = 0.9,
    train_max_pairs: float = 1e7,
    dry_run: bool = False,
) -> str:
    """Resolve one entity pool end to end. Returns the output table name.

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

    db_api = PostgresAPI(engine=engine)
    linker = Linker(input_name, settings, db_api=db_api)
    logger.info("Linker built for {} on {}", entity, input_name)

    if dry_run:
        logger.success("Dry run OK — settings + linker valid for {}", entity)
        return spec.output_table

    logger.info("Estimating u via random sampling (max_pairs={:.0e}) …", train_max_pairs)
    linker.training.estimate_u_using_random_sampling(max_pairs=train_max_pairs)

    # EM on a couple of well-populated blocking rules.
    from splink import block_on
    for rule in (block_on("zip5"), block_on("state_code")):
        try:
            linker.training.estimate_parameters_using_expectation_maximisation(rule)
        except Exception as err:  # noqa: BLE001 — EM on a sparse rule may give up; keep going
            logger.warning("EM skipped for {}: {}", rule, err)

    logger.info("Predicting pairwise matches (threshold={}) …", match_threshold)
    predictions = linker.inference.predict(threshold_match_probability=match_threshold)

    logger.info("Clustering predictions …")
    clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
        predictions, threshold_match_probability=match_threshold
    )

    df = clusters.as_pandas_dataframe()
    keep = [c for c in ("cluster_id", spec.unique_id, "source_system", "source_pk") if c in df.columns]
    df = df[keep].rename(columns={"cluster_id": f"master_{spec.name}_id"})
    df.to_sql(
        spec.output_table.split(".", 1)[1],
        engine,
        schema=spec.output_table.split(".", 1)[0],
        if_exists="replace",
        index=False,
        chunksize=10_000,
    )
    logger.success("Wrote {:,} cluster rows to {}", len(df), spec.output_table)
    return spec.output_table
