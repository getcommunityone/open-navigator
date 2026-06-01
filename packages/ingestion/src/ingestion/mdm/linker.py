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
}


def _prepare_input(engine, spec: EntitySpec) -> str:
    """Return the table/view name Splink should read.

    For a filtered pool (person), materialise a view so Splink sees only the
    relevant entity_type without us mutating the source.
    """
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
    return spec.output_table
