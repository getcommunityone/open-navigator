"""Write the data-dictionary ERDs of a dbt project's models.

    python -m erd --models dbt_project/models/marts --out web_docs/static/img/erd --name marts

writes <out>/<name>_full.drawio (every column) and <out>/<name>_entity.drawio (the same arrangement, keys only).
Render them to PNG with `node packages/erd/src/erd/drawio_render.js <files>` (needs playwright).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from .dbt_model import build_model, read_models
from .dictionary import write


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m erd", description=__doc__.split("\n\n")[0])
    parser.add_argument("--models", type=Path, nargs="+", required=True, help="schema.yml files or folders")
    parser.add_argument("--out", type=Path, required=True, help="folder for the .drawio files")
    parser.add_argument("--name", default="marts", help="file prefix")
    parser.add_argument("--page-columns", type=int, default=4)
    args = parser.parse_args(argv)
    models = read_models(args.models)
    if not models:
        raise SystemExit(f"no dbt models found under {', '.join(map(str, args.models))}")
    model = build_model(models, args.page_columns)
    logger.info("{} models, {} relationships, {} subject areas", len(model.TABLES), len(model.RELATIONSHIPS),
                len(model.GROUPS))
    for path in write(args.name, model, None, args.out):
        logger.success("wrote {}", path)


if __name__ == "__main__":
    main()
