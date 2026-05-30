#!/usr/bin/env python3
"""Export the served FastAPI app's OpenAPI schema to a JSON file.

The deployed API is ``api.app:app`` (see ``Dockerfile.app``). Producing the
schema requires importing the full app, so run this where the backend deps are
installed (CI's backend job, or a local backend venv) — not from a bare
frontend checkout.

Consumed by the frontend codegen (``npm run gen:api``) to compile strict
TypeScript types from the live backend contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "openapi.json",
        help="Path to write the OpenAPI JSON (default: <repo-root>/openapi.json)",
    )
    args = parser.parse_args()

    # Make the repo importable no matter where this is invoked from (the npm
    # script runs it with cwd=web_app/).
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    # Imported lazily so `--help` works without the backend installed.
    from api.app import app

    schema = app.openapi()
    if not schema.get("paths"):
        print("ERROR: generated OpenAPI schema has no paths", file=sys.stderr)
        return 1

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys keeps output byte-stable so type-drift diffs stay meaningful.
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {out} ({len(schema['paths'])} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
