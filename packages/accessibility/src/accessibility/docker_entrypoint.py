#!/usr/bin/env python3
"""Container entrypoint: discover PDFs → veraPDF → optional Postgres persist."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--batch-id", default="")
    ap.add_argument("--max-pdfs-per-site", type=int, default=3)
    ap.add_argument("--no-persist", action="store_true")
    args, _ = ap.parse_known_args()

    cache = _ROOT / "data" / "cache" / "accessibility"
    cache.mkdir(parents=True, exist_ok=True)
    manifest = cache / "pdf-urls-docker.json"
    py = sys.executable

    disc = [
        py,
        "-m",
        "accessibility.export_pdf_urls",
        "--out",
        str(manifest),
        "--max-pdfs-per-site",
        str(args.max_pdfs_per_site),
    ]
    if args.state:
        disc.extend(["--state", args.state])
    if args.limit:
        disc.extend(["--limit", str(args.limit)])
    if args.offset:
        disc.extend(["--offset", str(args.offset)])
    if args.batch_id:
        disc.extend(["--batch-id", args.batch_id])
    subprocess.run(disc, check=True, cwd=str(_ROOT))

    import json

    batch_id = json.loads(manifest.read_text(encoding="utf-8")).get("batch_id", "docker")
    out = cache / f"verapdf-{batch_id}.ndjson"
    scan = [py, "-m", "accessibility.run_verapdf_scan", "--manifest", str(manifest), "--out", str(out)]
    if args.limit:
        scan.extend(["--limit", str(args.limit)])
    subprocess.run(scan, check=True, cwd=str(_ROOT))

    if not args.no_persist:
        subprocess.run(
            [py, "-m", "accessibility.persist_verapdf_results", "--input", str(out), "--ensure-ddl"],
            check=True,
            cwd=str(_ROOT),
        )


if __name__ == "__main__":
    main()
