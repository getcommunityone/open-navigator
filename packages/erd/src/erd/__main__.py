"""Write the data-dictionary ERDs of a dbt project's models.

    python -m erd --models dbt_project/models/marts --out web_docs/static/img/erd --name marts

By default writes one entity and one full diagram per subject area
(`<out>/<name>_<area>_{entity,full}.drawio`). Pass `--one-canvas` for the old single mega pair.
Render them to PNG with `node packages/erd/src/erd/drawio_render.js <files>` (needs playwright).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from .dbt_model import build_model, read_models
from .dictionary import write
from .stats import measured_note, table_stats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m erd", description=__doc__.split("\n\n")[0])
    parser.add_argument("--models", type=Path, nargs="+", required=True, help="schema.yml files or folders")
    parser.add_argument("--out", type=Path, required=True, help="folder for the .drawio files")
    parser.add_argument("--name", default="marts", help="file prefix")
    parser.add_argument("--page-columns", type=int, default=4)
    parser.add_argument("--one-canvas", action="store_true",
                        help="one entity/full pair with every area on one canvas (huge; not for viewing)")
    parser.add_argument("--dsn", help="Postgres URL: show each table's exact row count and the area totals "
                                      "(needs `pip install 'communityone-erd[db]'`)")
    parser.add_argument("--schema", default="gold", help="schema the models are built in (with --dsn)")
    args = parser.parse_args(argv)
    models = read_models(args.models)
    if not models:
        raise SystemExit(f"no dbt models found under {', '.join(map(str, args.models))}")
    model = build_model(models, args.page_columns)
    logger.info("{} models, {} relationships, {} subject areas", len(model.TABLES), len(model.RELATIONSHIPS),
                len(model.GROUPS))
    stats = None
    if args.dsn:
        stats = table_stats(args.dsn, args.schema, list(model.TABLES))
        model.STATS_NOTE = measured_note(args.schema)
        logger.info("measured {} of {} tables in {}; the rest are not built there", len(stats), len(model.TABLES),
                    args.schema)
    for path in write(args.name, model, stats, args.out, per_area=not args.one_canvas):
        logger.success("wrote {}", path)


if __name__ == "__main__":
    main()
