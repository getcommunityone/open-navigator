"""Bring a Colab Gemma run's analyses into the policy cache through the pipeline's own save path (#511).

Runs on the laptop, after the run folder ``<out>/<run_date>/`` has been copied down from Drive or the landing volume.
For each ``<video_id>.analysis.json`` with its ``.meta.json`` and ``.response.txt`` it rebuilds the exported request
and calls ``meeting_transcript_policy.save_part1_response`` with the raw answer, exactly as the Gemini Batch collect
does: the same normalisation, date check, legislation enrichment, file layout (``02_analysis`` / ``04_runs``), bronze
stamps and ``persist_policy_analysis_bronze``. The meta records ``gemini_model`` = the Gemma model, so
``load_analysis_cache_to_bronze`` writes it to ``bronze_events_analysis_ai.ai_model`` and dbt carries it to
``event_decision.source_ai_model``; ``backend``, ``quantization``, GPU, transformers version, decoding, seconds and
tokens ride along in the meta.

    python -m llm.gpu.colab_policy_import --run data/cache/colab_gemma_runs/2026-11-18 \\
        --bundle data/cache/colab_gemma_export/2026-11-17 --dry-run
    python -m llm.gpu.colab_policy_import --run data/cache/colab_gemma_runs/2026-11-18 \\
        --bundle data/cache/colab_gemma_export/2026-11-17

Then the usual path: ``python -m ingestion.youtube.promote_to_c1_event`` ->
``python -m llm.enrichment.load_analysis_cache_to_bronze`` -> dbt.

Skipped, never overwritten: pilot meetings (they have a Gemini analysis; the pilot is for comparison), a meeting that
already has an analysis in the cache, and any meeting whose meta says it wasn't valid. ``--include-pilot`` lifts the
first rule only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
META_KEYS = ("model", "backend", "quantization", "gpu_name", "transformers_version", "decoding", "seconds",
             "attempts", "compute_units", "compute_units_source", "prompt_version", "prompt_sha256", "run_date",
             "pilot", "status")


def import_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """The keys of the Colab meta that go into the cache's meta beside the pipeline's own."""
    out = {k: meta.get(k) for k in META_KEYS if k in meta}
    out["imported_from"] = "llm.gpu.colab_policy_import (#511)"
    return out


def plan_imports(run_dir: Path, *, include_pilot: bool = False) -> tuple[list[str], dict[str, str]]:
    """(video ids to import, {video id: why skipped}) from the run folder's files."""
    todo: list[str] = []
    skipped: dict[str, str] = {}
    for analysis in sorted(run_dir.glob("*.analysis.json")):
        vid = analysis.name[: -len(".analysis.json")]
        meta_path = run_dir / f"{vid}.meta.json"
        response = run_dir / f"{vid}.response.txt"
        if not meta_path.is_file() or not response.is_file():
            skipped[vid] = "meta or response missing"
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("backend") != "colab_hf" or not meta.get("model"):
            skipped[vid] = "meta has no colab_hf model"
        elif meta.get("status") not in ("ok", "no_items") or not meta.get("json_parsed"):
            skipped[vid] = f"status {meta.get('status')!r}"
        elif meta.get("pilot") and not include_pilot:
            skipped[vid] = "pilot meeting (compare only; --include-pilot to import)"
        else:
            todo.append(vid)
    return todo, skipped


def import_run(run_dir: Path, bundle_dir: Path, *, output_dir: Path, database_url: str, repo_root: Path = _REPO_ROOT,
               include_pilot: bool = False, dry_run: bool = False, save=None) -> dict[str, str]:
    """Import every eligible meeting; returns ``{video_id: outcome}``."""
    from llm.gemini.analyze_backlog import JurisdictionPlan, build_pipeline_namespace
    from llm.gemini.meeting_transcript_policy import Part1Request
    from llm.gemini.transcript_cache_paths import resolve_analysis_path

    if save is None:
        from llm.gemini.meeting_transcript_policy import save_part1_response as save
    todo, skipped = plan_imports(run_dir, include_pilot=include_pilot)
    outcomes: dict[str, str] = {vid: f"skipped: {why}" for vid, why in skipped.items()}
    for vid in todo:
        req_path = bundle_dir / "requests" / f"{vid}.json"
        if not req_path.is_file():
            outcomes[vid] = f"skipped: no request in {bundle_dir}/requests"
            continue
        data = json.loads(req_path.read_text(encoding="utf-8"))
        meta = json.loads((run_dir / f"{vid}.meta.json").read_text(encoding="utf-8"))
        request = Part1Request.from_json(data)
        request.model = meta["model"]
        request.out_dir = output_dir
        request.prompt_path = repo_root / "prompts" / f"{data.get('prompt_name') or 'policy_analysis_part_1'}.md"
        video = request.video
        existing = resolve_analysis_path(output_dir, video.jurisdiction_id, video_id=video.video_id,
                                         title=video.title or "", event_date=video.event_date,
                                         state_code=request.state_code, channel_id=getattr(video, "channel_id", None))
        if existing is not None:
            outcomes[vid] = f"skipped: already analyzed ({existing.name})"
            continue
        if dry_run:
            outcomes[vid] = "would import"
            continue
        plan = JurisdictionPlan(jurisdiction_id=video.jurisdiction_id, state_code=request.state_code or "",
                                pending=0, newest_pending=None)
        ns = build_pipeline_namespace(plan, model=request.model, database_url=database_url, limit=None)
        ns.output_dir = output_dir
        try:
            save(request, (run_dir / f"{vid}.response.txt").read_text(encoding="utf-8"), ns,
                 usage=meta.get("usage"), generation_source="colab_hf", pipeline="colab_gemma_policy",
                 extra_meta=import_meta(meta))
            outcomes[vid] = "imported"
            logger.success("imported {} ({})", vid, request.model)
        except Exception as exc:  # noqa: BLE001 - one bad meeting never stops the import
            outcomes[vid] = f"failed: {type(exc).__name__}: {str(exc)[:200]}"
            logger.error("{}: {}", vid, outcomes[vid])
    return outcomes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m llm.gpu.colab_policy_import",
                                description="Save a Colab Gemma run into the policy cache (#511).")
    p.add_argument("--run", type=Path, required=True, help="the run folder copied down: <out>/<run_date>")
    p.add_argument("--bundle", type=Path, required=True, help="the export bundle the run used")
    p.add_argument("--output-dir", type=Path, default=_REPO_ROOT / "data" / "cache" / "gemini_transcript_policy",
                   help="policy cache root")
    p.add_argument("--database-url", default=None, help="default OPEN_NAVIGATOR_DATABASE_URL, else localhost:5433")
    p.add_argument("--include-pilot", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    from llm.gpu.colab_policy_export import resolve_database_url

    args = build_parser().parse_args(argv)
    outcomes = import_run(args.run, args.bundle, output_dir=args.output_dir,
                          database_url=resolve_database_url(args.database_url), include_pilot=args.include_pilot,
                          dry_run=args.dry_run)
    for vid, outcome in sorted(outcomes.items()):
        print(f"{vid}  {outcome}")
    failed = [v for v, o in outcomes.items() if o.startswith("failed")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
