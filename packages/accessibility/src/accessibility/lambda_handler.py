#!/usr/bin/env python3
"""
AWS Lambda entrypoint for sharded accessibility scans.

Event shape (API Gateway / Step Functions):
  {
    "engine": "axe",
    "state": "AL",
    "offset": 0,
    "limit": 50,
    "batch_id": "20260515-shard-0",
    "persist": true
  }

Engines:
  - ``axe`` / ``pa11y`` — HTML WCAG (Chromium in container image)
  - ``lighthouse`` — Lighthouse audits (Chrome Launcher; use the same ``batch_id`` as axe to join in SQL)
  - ``verapdf`` — PDF/UA (container from ``docker/Dockerfile.verapdf-worker``;
    ``VERAPDF_USE_DOCKER=false`` in-image)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _persist_cmd(
    py: str, engine: str, result_path: Path, batch_id: str
) -> Tuple[str, List[str]]:
    if engine == "verapdf":
        return (
            "scripts.accessibility.persist_verapdf_results",
            ["--input", str(result_path), "--ensure-ddl"],
        )
    if engine == "lighthouse":
        return (
            "scripts.accessibility.persist_lighthouse_results",
            ["--input", str(result_path), "--batch-id", batch_id, "--ensure-ddl"],
        )
    return (
        "scripts.accessibility.persist_results",
        ["--scanner", engine, "--input", str(result_path), "--batch-id", batch_id, "--ensure-ddl"],
    )


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    engine = (event.get("engine") or "axe").strip().lower()
    state = event.get("state")
    offset = int(event.get("offset") or 0)
    limit = int(event.get("limit") or 50)
    batch_id = (event.get("batch_id") or "").strip() or f"lambda-{context.aws_request_id}"
    persist = bool(event.get("persist", True))

    cache = _ROOT / "tmp" / "accessibility" / batch_id
    cache.mkdir(parents=True, exist_ok=True)
    py = os.environ.get("LAMBDA_PYTHON", sys.executable)
    acc_dir = _ROOT / "scripts" / "accessibility"
    node = os.environ.get("NODE_BIN", "node")

    if engine == "verapdf":
        manifest = cache / "pdf-urls.json"
        export_pdf = [
            py,
            "-m",
            "scripts.accessibility.export_pdf_urls",
            "--out",
            str(manifest),
            "--limit",
            str(limit),
            "--offset",
            str(offset),
            "--batch-id",
            batch_id,
        ]
        if state:
            export_pdf.extend(["--state", str(state)])
        subprocess.run(export_pdf, check=True, cwd=str(_ROOT))
        result_path = cache / f"verapdf-{batch_id}.ndjson"
        subprocess.run(
            [
                py,
                "-m",
                "scripts.accessibility.run_verapdf_scan",
                "--manifest",
                str(manifest),
                "--out",
                str(result_path),
            ],
            check=True,
            cwd=str(_ROOT),
        )
    else:
        urls_file = cache / "urls.json"
        export_html = [
            py,
            "-m",
            "scripts.accessibility.export_urls",
            "--out",
            str(urls_file),
            "--limit",
            str(limit),
            "--offset",
            str(offset),
            "--batch-id",
            batch_id,
        ]
        if state:
            export_html.extend(["--state", str(state)])
        subprocess.run(export_html, check=True, cwd=str(_ROOT))

        if engine == "axe":
            result_path = cache / "results.ndjson"
            subprocess.run(
                [node, "run_axe_scan.mjs", "--urls", str(urls_file), "--out", str(result_path)],
                check=True,
                cwd=str(acc_dir),
            )
        elif engine == "lighthouse":
            result_path = cache / f"lighthouse-{batch_id}.ndjson"
            subprocess.run(
                [
                    node,
                    "run_lighthouse_scan.mjs",
                    "--urls",
                    str(urls_file),
                    "--out",
                    str(result_path),
                ],
                check=True,
                cwd=str(acc_dir),
            )
        elif engine == "pa11y":
            subprocess.run(
                [node, "run_pa11y_workers.mjs", "--urls", str(urls_file), "--out", str(cache / "pa11y")],
                check=True,
                cwd=str(acc_dir),
            )
            result_path = cache / "pa11y" / "pa11y-results-merged.json"
        else:
            raise ValueError(f"unsupported engine: {engine}")

    if persist:
        mod, extra = _persist_cmd(py, engine, result_path, batch_id)
        subprocess.run([py, "-m", mod, *extra], check=True, cwd=str(_ROOT))

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "batch_id": batch_id,
                "engine": engine,
                "offset": offset,
                "limit": limit,
                "result_path": str(result_path),
            }
        ),
    }
