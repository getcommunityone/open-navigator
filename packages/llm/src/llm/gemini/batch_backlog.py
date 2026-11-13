"""
Run the transcript-analysis backlog through the Gemini Batch API (#264).

The interactive driver (``llm.gemini.analyze_backlog``) sends one synchronous
call per transcript. Nothing needs those answers within seconds, so this sends
the same Part 1 requests as a file: Google answers within a day and bills batch
requests at a discount, and no connection is held open per transcript (no
hangs, 504s or retry storms).

Three steps, each safe to re-run::

    # 1. Build the requests for pending transcripts and create the job(s)
    python -m llm.gemini.batch_backlog submit --state AL
    python -m llm.gemini.batch_backlog submit --jurisdiction-id municipality_0177256 --state AL --limit 50
    python -m llm.gemini.batch_backlog submit --state AL --dry-run     # write the files, create no job

    # 2. See where the jobs are
    python -m llm.gemini.batch_backlog status

    # 3. Save the finished jobs' analyses (same files and bronze stamps as the interactive pipeline)
    python -m llm.gemini.batch_backlog collect
    python -m llm.gemini.batch_backlog collect --wait                  # poll until every job has ended

A request is built by the same code the interactive pipeline uses
(``prepare_part1_request``) and a response is saved by the same code
(``save_part1_response``), so the two produce the same analysis files.

Each job has a folder under ``--jobs-dir`` (default
``data/cache/gemini_batch_jobs/``)::

    <job_id>/manifest.json          job name, model, state, video ids, per-video result
    <job_id>/requests.jsonl         the uploaded file, one request per line
    <job_id>/requests/<video>.json  what saving that video's response needs
    <job_id>/results.jsonl          the downloaded results

A video in a job that has not ended, or has ended and not been collected, is
not submitted again. A request that failed is stamped as a failed analysis and
is picked up by the next ``submit``.

Limits: a batch job belongs to the API key that created it, so ``status`` and
``collect`` must run with the same ``GEMINI_API_KEY`` as ``submit`` (the key
pool is not rotated). ``--diarize`` is not supported: it needs a GPU at submit
time. Part 2 (the Markdown report) is not run, as in ``analyze_backlog``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from llm.gemini.genai_text_client import (
    default_flash_lite_model,
    supports_thinking_budget,
)

JOBS_DIRNAME = "gemini_batch_jobs"
DEFAULT_MAX_REQUESTS_PER_JOB = 500

# Batch job states (google.genai.types.JobState names).
SUCCEEDED = "JOB_STATE_SUCCEEDED"
ENDED_WITHOUT_RESULTS = {"JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
DRY_RUN = "DRY_RUN"  # files written, no job created


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested; no network, no database)
# --------------------------------------------------------------------------- #
def default_jobs_dir(output_dir: Path) -> Path:
    """Beside the policy cache, not inside it: the cache's own tools walk its folders."""
    return Path(output_dir).resolve().parent / JOBS_DIRNAME


def new_job_id(now: datetime | None = None, *, sequence: int = 1) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{sequence:03d}"


def build_request_line(
    video_id: str,
    user_message: str,
    *,
    model: str,
    temperature: float,
    max_output_tokens: int,
    thinking_budget: int | None,
    json_mode: bool,
    system_instruction: str = "",
) -> dict[str, Any]:
    """One line of the batch input file. The same generation settings as the
    interactive Part 1 call (``call_gemini_text``)."""
    generation_config: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if thinking_budget is not None and supports_thinking_budget(model):
        generation_config["thinking_config"] = {"thinking_budget": int(thinking_budget)}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"
    request: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generation_config": generation_config,
    }
    if system_instruction.strip():
        request["system_instruction"] = {"parts": [{"text": system_instruction.strip()}]}
    return {"key": video_id, "request": request}


def parse_result_line(line: str) -> tuple[str, str | None, dict[str, Any] | None, str | None] | None:
    """``(key, text, response, error)`` for one line of a results file.

    ``text`` is the answer (thought parts left out) and ``response`` the raw
    response object (for its ``usageMetadata``); on a failed request ``text`` is
    ``None`` and ``error`` says why. ``None`` for a line that isn't a result.
    """
    line = line.strip()
    if not line:
        return None
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict) or not row.get("key"):
        return None
    key = str(row["key"])
    if row.get("error"):
        err = row["error"]
        message = err.get("message") if isinstance(err, dict) else None
        return key, None, None, str(message or err)[:2000]
    response = row.get("response")
    if not isinstance(response, dict):
        return key, None, None, "result line has no response"
    candidates = response.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    text = "".join(p.get("text") or "" for p in parts if isinstance(p, dict) and not p.get("thought"))
    if not text.strip():
        reason = (candidates[0].get("finishReason") if candidates else None) or "no candidates"
        return key, None, response, f"empty response ({reason})"
    return key, text, response, None


def is_in_flight(manifest: dict[str, Any]) -> bool:
    """Whether a job's videos are still spoken for: it was created and has not
    ended without results, and its results have not been collected."""
    state = manifest.get("state") or ""
    if state == DRY_RUN or state in ENDED_WITHOUT_RESULTS:
        return False
    return not manifest.get("collected_at")


def in_flight_video_ids(manifests: Iterable[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for manifest in manifests:
        if is_in_flight(manifest):
            out.update(manifest.get("video_ids") or [])
    return out


def read_manifests(jobs_dir: Path) -> list[dict[str, Any]]:
    """Every job's manifest, oldest first; a folder with no readable manifest is skipped."""
    out: list[dict[str, Any]] = []
    if not Path(jobs_dir).is_dir():
        return out
    for path in sorted(Path(jobs_dir).glob("*/manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Unreadable manifest skipped: {}", path)
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def write_manifest(jobs_dir: Path, manifest: dict[str, Any]) -> Path:
    path = Path(jobs_dir) / manifest["job_id"] / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def chunked(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), max(1, size)):
        yield items[start : start + max(1, size)]


# --------------------------------------------------------------------------- #
# API edge
# --------------------------------------------------------------------------- #
def _batch_client() -> Any:
    """One client on the primary key: a job is only visible to the key that made it."""
    from llm.gemini.browser_policy_analysis import _REPO_ROOT
    from llm.gemini.genai_text_client import _client_for, ensure_valid_gemini_api_key

    return _client_for(ensure_valid_gemini_api_key(env_path=_REPO_ROOT / ".env"))


def _state_name(job: Any) -> str:
    state = getattr(job, "state", None)
    return str(getattr(state, "name", None) or state or "")


def create_job(client: Any, requests_file: Path, *, model: str, display_name: str) -> Any:
    from google.genai import types

    uploaded = client.files.upload(
        file=str(requests_file),
        config=types.UploadFileConfig(display_name=display_name, mime_type="jsonl"),
    )
    return client.batches.create(
        model=model, src=uploaded.name, config={"display_name": display_name}
    )


def refresh_state(client: Any, manifest: dict[str, Any]) -> Any:
    """Ask the API for the job's state and store it in the manifest (not yet written)."""
    job = client.batches.get(name=manifest["job_name"])
    manifest["state"] = _state_name(job)
    manifest["state_checked_at"] = datetime.now(UTC).isoformat()
    return job


# --------------------------------------------------------------------------- #
# submit
# --------------------------------------------------------------------------- #
def _plans(args: argparse.Namespace, database_url: str) -> list[Any]:
    from llm.gemini.analyze_backlog import (
        JurisdictionPlan,
        fetch_pending_plans,
        filter_plans,
        parse_states,
    )

    states = parse_states(getattr(args, "state", None))
    if (args.jurisdiction_id or "").strip():
        return [
            JurisdictionPlan(
                jurisdiction_id=args.jurisdiction_id.strip(),
                state_code=(states[0] if states else ""),
                pending=0,
                newest_pending=None,
            )
        ]
    plans = filter_plans(fetch_pending_plans(database_url, states=states), states=states)
    if args.max_jurisdictions is not None:
        plans = plans[: int(args.max_jurisdictions)]
    return plans


def _pipeline_namespace(args: argparse.Namespace, plan: Any, database_url: str) -> argparse.Namespace:
    """The interactive backlog's settings for one jurisdiction, plus this run's options."""
    from llm.gemini.analyze_backlog import build_pipeline_namespace

    ns = build_pipeline_namespace(
        plan,
        model=args.model,
        database_url=database_url,
        limit=args.limit_per_jurisdiction,
        prompt_file=args.prompt_file or "",
    )
    ns.output_dir = Path(args.output_dir)
    ns.thinking_budget = args.thinking_budget
    ns.no_json_mode = args.no_json_mode
    return ns


def prepare_requests(args: argparse.Namespace, database_url: str, skip: set[str]) -> list[Any]:
    """A ``Part1Request`` for each pending video, newest jurisdiction first, up to ``--limit``."""
    from llm.gemini.meeting_transcript_policy import (
        _policy_state_code,
        iter_videos_to_analyze,
        load_speaker_context,
        prepare_part1_request,
        select_bronze_videos,
    )
    from llm.gemini.transcript_cache_paths import resolve_canonical_jurisdiction_id

    requests: list[Any] = []
    for plan in _plans(args, database_url):
        if args.limit is not None and len(requests) >= args.limit:
            break
        ns = _pipeline_namespace(args, plan, database_url)
        jurisdiction_id = resolve_canonical_jurisdiction_id(plan.jurisdiction_id)
        state_code = _policy_state_code(ns)
        try:
            videos = select_bronze_videos(ns, jurisdiction_id)
        except SystemExit as exc:  # "No bronze videos for <id>": nothing to do there
            logger.warning("{}", exc)
            continue
        speaker_hints, known = load_speaker_context(ns, jurisdiction_id)
        for video in iter_videos_to_analyze(videos, ns, jurisdiction_id, state_code):
            if args.limit is not None and len(requests) >= args.limit:
                break
            if video.video_id in skip:
                logger.info("Skip {} — already in a batch job that has not been collected", video.video_id)
                continue
            try:
                request = prepare_part1_request(video, ns, speaker_hints=speaker_hints, known=known)
            except Exception as exc:  # noqa: BLE001 - one bad transcript must not stop the submit
                logger.warning("Skip {} — could not build its request: {}", video.video_id, exc)
                continue
            if request is not None:
                requests.append(request)
                skip.add(video.video_id)
    return requests


def write_job_files(jobs_dir: Path, job_id: str, requests: list[Any], args: argparse.Namespace) -> Path:
    """``requests.jsonl`` and one sidecar per video. Returns the JSONL path."""
    job_dir = Path(jobs_dir) / job_id
    (job_dir / "requests").mkdir(parents=True, exist_ok=True)
    requests_file = job_dir / "requests.jsonl"
    with requests_file.open("w", encoding="utf-8") as fh:
        for request in requests:
            video_id = request.video.video_id
            line = build_request_line(
                video_id,
                request.user_message,
                model=request.model,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                thinking_budget=None if args.thinking_budget < 0 else args.thinking_budget,
                json_mode=not args.no_json_mode,
                system_instruction=args.system_instruction,
            )
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            (job_dir / "requests" / f"{video_id}.json").write_text(
                json.dumps(request.to_json(), ensure_ascii=False) + "\n", encoding="utf-8"
            )
    return requests_file


def run_submit(args: argparse.Namespace) -> list[dict[str, Any]]:
    from llm.gemini.analyze_backlog import _resolve_database_url

    if not (args.model or "").strip():
        args.model = default_flash_lite_model()
    jobs_dir = Path(args.jobs_dir) if args.jobs_dir else default_jobs_dir(args.output_dir)
    database_url = _resolve_database_url(args.database_url)
    skip = in_flight_video_ids(read_manifests(jobs_dir))
    if skip:
        logger.info("{:,} video(s) are in batch jobs not yet collected and will be skipped", len(skip))

    requests = prepare_requests(args, database_url, skip)
    if not requests:
        logger.success("Nothing to submit — no pending transcript outside the jobs already running.")
        return []

    client = None if args.dry_run else _batch_client()
    manifests: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    for sequence, chunk in enumerate(chunked(requests, args.max_requests_per_job), 1):
        job_id = new_job_id(now, sequence=sequence)
        requests_file = write_job_files(jobs_dir, job_id, chunk, args)
        manifest: dict[str, Any] = {
            "job_id": job_id,
            "job_name": None,
            "model": args.model,
            "state": DRY_RUN,
            "created_at": now.isoformat(),
            "request_count": len(chunk),
            "request_bytes": requests_file.stat().st_size,
            "jurisdiction_ids": sorted({r.video.jurisdiction_id for r in chunk}),
            "video_ids": [r.video.video_id for r in chunk],
            "collected_at": None,
            "results": {},
        }
        if client is not None:
            job = create_job(client, requests_file, model=args.model, display_name=f"transcript-part1-{job_id}")
            manifest["job_name"] = job.name
            manifest["state"] = _state_name(job)
        write_manifest(jobs_dir, manifest)
        manifests.append(manifest)
        logger.success(
            "{} {}: {:,} request(s), {:,} bytes, model {} ({})",
            "Wrote (dry run)" if client is None else "Created",
            manifest["job_name"] or job_id,
            len(chunk),
            manifest["request_bytes"],
            args.model,
            manifest["state"],
        )
    return manifests


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #
def _selected(manifests: list[dict[str, Any]], job: str | None) -> list[dict[str, Any]]:
    if not job:
        return manifests
    return [m for m in manifests if job in (m.get("job_id"), m.get("job_name"))]


def run_status(args: argparse.Namespace) -> list[dict[str, Any]]:
    jobs_dir = Path(args.jobs_dir) if args.jobs_dir else default_jobs_dir(args.output_dir)
    manifests = _selected(read_manifests(jobs_dir), args.job)
    if not manifests:
        logger.info("No batch jobs under {}", jobs_dir)
        return []
    client = None
    for manifest in manifests:
        if manifest.get("job_name") and is_in_flight(manifest) and manifest.get("state") != SUCCEEDED:
            client = client or _batch_client()
            try:
                refresh_state(client, manifest)
                write_manifest(jobs_dir, manifest)
            except Exception as exc:  # noqa: BLE001 - report what is known
                logger.warning("Could not read {}: {}", manifest["job_name"], exc)
        results = manifest.get("results") or {}
        saved = sum(1 for v in results.values() if v == "saved")
        logger.info(
            "{}  {}  requests={:,}  state={}  collected={}  saved={:,}  failed={:,}",
            manifest["job_id"],
            manifest.get("job_name") or "-",
            manifest.get("request_count") or 0,
            manifest.get("state"),
            "yes" if manifest.get("collected_at") else "no",
            saved,
            sum(1 for v in results.values() if str(v).startswith("failed")),
        )
    return manifests


# --------------------------------------------------------------------------- #
# collect
# --------------------------------------------------------------------------- #
def _save_namespace(args: argparse.Namespace) -> argparse.Namespace:
    """Save settings: the interactive backlog's (bronze persisted, no Part 2)."""
    from llm.gemini.meeting_transcript_policy import build_parser

    ns = build_parser().parse_args([])
    ns.persist_bronze = not getattr(args, "no_persist_bronze", False)
    ns.run_part_2 = False
    ns.database_url = args.database_url or ""
    return ns


def collect_results(
    job_dir: Path,
    manifest: dict[str, Any],
    lines: Iterable[str],
    save_args: argparse.Namespace,
) -> dict[str, str]:
    """Save every result line of one job. Returns ``{video_id: outcome}`` where the
    outcome is ``"saved"``, ``"already saved"`` or ``"failed: <why>"``. A video whose
    analysis already exists is left as it is, so collecting twice rewrites nothing."""
    from llm.gemini.meeting_transcript_policy import (
        Part1Request,
        _record_policy_event_safe,
        save_part1_response,
    )
    from llm.gemini.transcript_cache_paths import resolve_analysis_path
    from llm.usage.calls import record_llm_call, usage_from_genai_response

    outcomes: dict[str, str] = {}
    for line in lines:
        parsed = parse_result_line(line)
        if parsed is None:
            continue
        video_id, text, response, error = parsed
        sidecar = job_dir / "requests" / f"{video_id}.json"
        if not sidecar.is_file():
            outcomes[video_id] = "failed: no request sidecar for this key"
            continue
        request = Part1Request.from_json(json.loads(sidecar.read_text(encoding="utf-8")))
        video = request.video
        existing = resolve_analysis_path(
            request.out_dir,
            video.jurisdiction_id,
            video_id=video.video_id,
            title=video.title or "",
            event_date=video.event_date,
            state_code=request.state_code,
            channel_id=getattr(video, "channel_id", None),
        )
        if existing is not None:
            outcomes[video_id] = "already saved"
            continue
        usage = usage_from_genai_response(response)
        labels = dict(stage="part1", video_id=video_id, jurisdiction_id=video.jurisdiction_id)
        if text is None:
            outcomes[video_id] = f"failed: {error}"
            record_llm_call(provider="gemini", model=request.model, usage=usage, is_ok=False,
                            error_type="BatchRequestFailed", api_mode="batch", **labels)  # fmt: skip
            _record_policy_event_safe(video_id, stage="analysis", ok=False, error=f"batch: {error}",
                                      database_url=save_args.database_url or None)  # fmt: skip
            continue
        try:
            save_part1_response(request, text, save_args, usage=usage.as_dict())
            outcomes[video_id] = "saved"
            record_llm_call(provider="gemini", model=request.model, usage=usage, is_ok=True,
                            api_mode="batch", **labels)  # fmt: skip
        except Exception as exc:  # noqa: BLE001 - one bad response must not stop the collect
            logger.exception("Could not save {}: {}", video_id, exc)
            outcomes[video_id] = f"failed: save error: {type(exc).__name__}: {exc}"[:2000]
            record_llm_call(provider="gemini", model=request.model, usage=usage, is_ok=False,
                            error_type=type(exc).__name__, api_mode="batch", **labels)  # fmt: skip
    for video_id in manifest.get("video_ids") or []:
        outcomes.setdefault(video_id, "failed: no result line for this key")
    return outcomes


def run_collect(args: argparse.Namespace) -> list[dict[str, Any]]:
    jobs_dir = Path(args.jobs_dir) if args.jobs_dir else default_jobs_dir(args.output_dir)
    save_args = _save_namespace(args)
    client = None
    collected: list[dict[str, Any]] = []
    while True:
        waiting = 0
        for manifest in _selected(read_manifests(jobs_dir), args.job):
            if not manifest.get("job_name") or not is_in_flight(manifest):
                continue
            client = client or _batch_client()
            job = refresh_state(client, manifest)
            job_dir = jobs_dir / manifest["job_id"]
            if manifest["state"] in ENDED_WITHOUT_RESULTS:
                logger.error("{} ended as {}: its videos are free to submit again",
                             manifest["job_name"], manifest["state"])  # fmt: skip
                write_manifest(jobs_dir, manifest)
                continue
            if manifest["state"] != SUCCEEDED:
                waiting += 1
                write_manifest(jobs_dir, manifest)
                logger.info("{} is {} — not ready", manifest["job_name"], manifest["state"])
                continue
            result_file = getattr(getattr(job, "dest", None), "file_name", None)
            if not result_file:
                logger.error("{} succeeded but names no result file", manifest["job_name"])
                continue
            data = client.files.download(file=result_file)
            (job_dir / "results.jsonl").write_bytes(data)
            outcomes = collect_results(job_dir, manifest, data.decode("utf-8").splitlines(), save_args)
            manifest["results"] = outcomes
            manifest["collected_at"] = datetime.now(UTC).isoformat()
            write_manifest(jobs_dir, manifest)
            collected.append(manifest)
            logger.success(
                "{}: saved {:,}, already saved {:,}, failed {:,}",
                manifest["job_name"],
                sum(1 for v in outcomes.values() if v == "saved"),
                sum(1 for v in outcomes.values() if v == "already saved"),
                sum(1 for v in outcomes.values() if v.startswith("failed")),
            )
        if not args.wait or waiting == 0:
            break
        logger.info("{} job(s) still running — checking again in {}s", waiting, args.poll_seconds)
        time.sleep(args.poll_seconds)
    if not collected:
        logger.info("No finished job to collect under {}", jobs_dir)
    return collected


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    from llm.gemini.browser_policy_analysis import DEFAULT_PROMPT_PART_1
    from llm.gemini.meeting_transcript_policy import DEFAULT_OUTPUT_DIR

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Policy cache root")
    common.add_argument("--jobs-dir", default="", help=f"Job folders (default: <output-dir>/../{JOBS_DIRNAME})")
    common.add_argument("--database-url", default="")

    parser = argparse.ArgumentParser(
        description="Run the transcript-analysis backlog through the Gemini Batch API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit", parents=[common], help="Build requests and create batch job(s)")
    submit.add_argument("--jurisdiction-id", default="", help="One jurisdiction (default: the whole pending backlog)")
    submit.add_argument("--state", action="append", default=None, help="State code(s), repeatable or comma-separated")
    submit.add_argument("--max-jurisdictions", type=int, default=None)
    submit.add_argument("--limit", type=int, default=None, help="Most requests to submit in this run")
    submit.add_argument("--limit-per-jurisdiction", type=int, default=None)
    submit.add_argument("--max-requests-per-job", type=int, default=DEFAULT_MAX_REQUESTS_PER_JOB,
                        help="Requests per job file; more than this are split across jobs")  # fmt: skip
    submit.add_argument("--model", default="", help="Model (default: GEMINI_FLASH_LITE_MODEL or gemini-2.5-flash-lite)")
    submit.add_argument("--prompt-file", default=str(DEFAULT_PROMPT_PART_1))
    submit.add_argument("--system-instruction", default="")
    submit.add_argument("--temperature", type=float, default=0.1)
    submit.add_argument("--max-output-tokens", type=int, default=65536)
    submit.add_argument("--thinking-budget", type=int, default=int(os.getenv("GEMINI_THINKING_BUDGET", "0")),
                        help="Thinking-token cap for gemini-2.5-flash* (0 = off, -1 = the model's default)")  # fmt: skip
    submit.add_argument("--no-json-mode", action="store_true")
    submit.add_argument("--dry-run", action="store_true", help="Write the job files and create no job")
    submit.set_defaults(func=run_submit)

    status = sub.add_parser("status", parents=[common], help="Print each job's state")
    status.add_argument("--job", default="", help="A job id or job name (default: all)")
    status.set_defaults(func=run_status)

    collect = sub.add_parser("collect", parents=[common], help="Save finished jobs' analyses")
    collect.add_argument("--job", default="", help="A job id or job name (default: all)")
    collect.add_argument("--wait", action="store_true", help="Poll until every selected job has ended")
    collect.add_argument("--poll-seconds", type=int, default=120)
    collect.add_argument("--no-persist-bronze", action="store_true",
                         help="Write the analysis files only; skip the bronze upserts (no warehouse at hand)")  # fmt: skip
    collect.set_defaults(func=run_collect)
    return parser


def main() -> None:
    from dotenv import load_dotenv

    from llm.gemini.browser_policy_analysis import _REPO_ROOT

    load_dotenv(_REPO_ROOT / ".env")
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
