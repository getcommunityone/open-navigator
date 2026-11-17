"""The meeting policy analysis (Part 1) with Gemma 4 on the owner's Colab GPU, from exported requests (#511).

Same prompt, same output schema, same meta as ``llm.gemini.meeting_transcript_policy``; only the model and where it
runs differ. Prepaid Colab compute units are used instead of the paid Gemini API. The notebook
``notebooks/colab_gemma_policy_analysis.ipynb`` is a thin shell around this module; the steps are in
``web_docs/docs/deployment/colab-gemma-policy-analysis.md``.

    python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt --pilot 3
    python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt --limit 20
    python -m llm.gpu.colab_policy_analyze --videos-file policy_export/2026-11-17/videos.txt \\
        --model gemma-4-26b-a4b-it --dry-run

- **Input:** the bundle written on the laptop by ``llm.gpu.colab_policy_export``: ``requests/<video_id>.json`` holds
  the exact Part 1 message the Gemini pipeline would send (prompt, MEDIA CONTEXT, transcript from
  ``bronze_event_youtube_transcript``). No YouTube and no database on Colab.
- **Model:** ``google/gemma-4-31B-it`` by default, ``--model gemma-4-26b-a4b-it`` for the faster mixture-of-experts
  one. Hugging Face transformers, 4-bit (bitsandbytes NF4) when the GPU has under 70 GB, else bf16
  (``--quantize auto``). Greedy decoding (deterministic). A prompt that doesn't fit the model's context fails clearly;
  the Gemini pipeline doesn't chunk transcripts, so this doesn't either.
- **Validation:** every answer is checked against ``llm.gemini.part1_schema``. An invalid one gets one repair turn
  (the errors, and "reply with the corrected JSON only"); still invalid means failed. A failed meeting writes
  ``<video_id>.failed.json`` and no analysis: nothing partial or invented is ever written as a result.
- **Output:** ``<out>/<run_date>/<video_id>.analysis.json`` (the validated answer), ``<video_id>.meta.json`` (the
  pipeline's meta keys plus ``model``, ``backend=colab_hf``, ``quantization``, GPU, ``prompt_version``, transformers
  version, decoding settings, seconds, tokens), ``<video_id>.response.txt`` (the raw answer, which the laptop import
  saves through the pipeline's own save path), and a run-level ``meta.json``.
- **Resume:** a video whose ``.analysis.json`` exists in the run folder is skipped; a failed one is tried again.
- **Usage:** per meeting, an ``llm.usage`` ``gpu_runs`` row (``gpu_run``) and an ``llm_calls`` row per generation,
  copied to ``<run>/llm_usage/``, plus a row in ``<run>/usage.jsonl`` with compute units (CU) estimated from GPU
  seconds. ``record_measured_cu`` adds the batch's measured CU (the owner's before/after balance) and apportions it
  to each meeting by GPU seconds, labelled an estimate.
- **Pilot:** ``--pilot N`` runs N meetings from ``pilot_videos.txt`` (they already have a Gemini analysis) and writes
  them as an arm of a ``llm.gemini.compare_models`` run folder, ``<run>/comparison/``. Score it with
  ``python -m llm.gemini.compare_models --rescore <run>/comparison`` (on the laptop, or here when the full ``llm``
  dependencies are installed): agreement with the Gemini analysis, quotes found verbatim in the transcript, tokens,
  seconds and CU per meeting, comparable with every other model run.

A GPU run starts only on the owner's explicit yes for that run (``AGENTS.md``, "GPU and paid compute").
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from loguru import logger

from llm.gemini.part1_schema import ValidationResult, parse_and_validate
from llm.gpu.colab_io import (
    COLAB_CU_PER_HOUR,
    COLAB_USD_PER_CU,
    DRIVE_ROOT,
    LANDING_VOLUME,
    Store,
    apportion,
    check_run_date,
    clean_rel,
    estimated_compute_units,
    get_secret,
    gpu_kind,
    make_store,
    measured_batch_cu,
    redact,
    today_utc,
)
from llm.prompt_version import prompt_version_label

DEFAULT_MODEL = "google/gemma-4-31B-it"
FAST_MODEL = "google/gemma-4-26B-A4B-it"
MODEL_ALIASES = {
    "gemma-4-31b-it": DEFAULT_MODEL,
    "google/gemma-4-31b-it": DEFAULT_MODEL,
    "31b": DEFAULT_MODEL,
    "gemma-4-26b-a4b-it": FAST_MODEL,
    "google/gemma-4-26b-a4b-it": FAST_MODEL,
    "26b": FAST_MODEL,
}
BACKEND = "colab_hf"
PLATFORM = "colab"
STEP_NAME = "gemma_policy_analysis"
PIPELINE = "colab_gemma_policy"
DEFAULT_OUT = "policy_analysis"
DEFAULT_MAX_NEW_TOKENS = 32768        # Gemma 4's output ceiling on the Gemini API (compare_models caps it the same)
BF16_MIN_GPU_GB = 70.0                # under this, 4-bit
DEFAULT_LIMIT = 200
TOKEN_NAMES = ("DATABRICKS_TOKEN", "HF_TOKEN")
SECRET_NAMES = ("HF_TOKEN", "DATABRICKS_HOST", "DATABRICKS_TOKEN")
NO_ITEMS_ERROR = "No decisions or uncontested items extracted from transcript."
REPAIR_INSTRUCTION = (
    "Your reply above is not a valid answer: it must be one JSON object matching the JSON Schema in the "
    "instructions, and nothing else.\n\nProblems found:\n{errors}\n\n{cut}Reply again with the corrected JSON "
    "object only: no markdown fence, no commentary. Use only what the transcript says; do not invent values. "
    "Where a required id is missing, add it; where you can't support a row from the transcript, drop the row."
)
CUT_NOTE = ("Your reply was cut off at the output limit. Keep every decision and uncontested item, but write the "
            "narrative fields more briefly so the whole object fits.\n\n")


# ------------------------------------------------------------------------------------------------- plain helpers
def resolve_model(name: str | None) -> str:
    """A Hugging Face repo id from an alias (``gemma-4-26b-a4b-it``) or the repo id itself."""
    raw = (name or DEFAULT_MODEL).strip()
    return MODEL_ALIASES.get(raw.lower(), raw)


def choose_quantization(requested: str, gpu_memory_gb: float | None) -> str:
    """``4bit`` or ``bf16``. ``auto``: 4-bit when the GPU has under 70 GB (or its size is unknown)."""
    req = (requested or "auto").strip().lower()
    if req == "4bit":
        return "4bit"
    if req in ("none", "bf16"):
        return "bf16"
    if req != "auto":
        raise ValueError(f"--quantize must be auto, 4bit or none, got {requested!r}")
    return "bf16" if gpu_memory_gb is not None and gpu_memory_gb >= BF16_MIN_GPU_GB else "4bit"


def arm_label(model: str, quantization: str) -> str:
    """The comparison arm for this model and precision, e.g. ``google/gemma-4-31B-it@colab_hf-4bit``.
    (``compare_models`` reads ``model:budget``, so a label never holds a colon or comma.)"""
    return f"{model}@{BACKEND}-{quantization}".replace(":", "-").replace(",", "-")


def arm_slug(label: str) -> str:
    """The file stem ``compare_models.Arm.slug`` gives the label."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", label)


def build_messages(user_message: str, system_instruction: str = "") -> list[dict[str, Any]]:
    """The chat turns for one meeting: the pipeline's Part 1 message as the user turn (its system instruction is
    empty by default, as here)."""
    messages: list[dict[str, Any]] = []
    if system_instruction.strip():
        messages.append({"role": "system", "content": [{"type": "text", "text": system_instruction.strip()}]})
    messages.append({"role": "user", "content": [{"type": "text", "text": user_message}]})
    return messages


def repair_messages(messages: list[dict[str, Any]], bad_answer: str, result: ValidationResult) -> list[dict[str, Any]]:
    """The one repair turn: the model's answer, then what's wrong with it."""
    errors = "\n".join(f"- {e}" for e in (result.errors or ["the reply is not valid"]))
    text = REPAIR_INSTRUCTION.format(errors=errors, cut=CUT_NOTE if result.truncated else "")
    return [*messages,
            {"role": "assistant", "content": [{"type": "text", "text": bad_answer}]},
            {"role": "user", "content": [{"type": "text", "text": text}]}]


def run_dir_rel(out: str, run_date: str) -> str:
    return posixpath.join(clean_rel(out), check_run_date(run_date))


def bundle_rel(videos_file: str) -> str:
    """The bundle folder: the folder that holds the videos file."""
    return posixpath.dirname(clean_rel(videos_file))


def output_names(video_id: str) -> dict[str, str]:
    return {k: f"{video_id}.{k}{ext}" for k, ext in
            (("analysis", ".json"), ("meta", ".json"), ("response", ".txt"), ("failed", ".json"))}


def split_done(video_ids: list[str], existing: Iterable[str]) -> tuple[list[str], list[str]]:
    """(to run, already done): done means the run folder has the video's ``.analysis.json``."""
    have = set(existing)
    todo, done = [], []
    for vid in video_ids:
        (done if output_names(vid)["analysis"] in have else todo).append(vid)
    return todo, done


def read_ids(text: str | None) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        vid = line.split("#", 1)[0].strip()
        if vid and vid not in out:
            out.append(vid)
    return out


def request_transcript(request: dict[str, Any]) -> str:
    """The caption text of a request, for the verbatim-quote check."""
    from llm.gpu.colab_policy_export import transcript_text

    return transcript_text(request)


# --------------------------------------------------------------------------------------------------- generation
@dataclass
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    seconds: float
    hit_limit: bool


class Generator(Protocol):
    model_id: str
    quantization: str
    context_tokens: int | None
    max_new_tokens: int
    transformers_version: str | None

    def count_tokens(self, messages: list[dict[str, Any]]) -> int: ...
    def generate(self, messages: list[dict[str, Any]]) -> Generation: ...


class ContextTooLong(RuntimeError):
    pass


class HFGemmaGenerator:
    """Gemma 4 through transformers on the local GPU: 4-bit NF4 (bitsandbytes) or bf16, greedy decoding."""

    def __init__(self, model_id: str, quantization: str, *, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
                 hf_token: str | None = None):
        import torch
        import transformers
        from transformers import AutoProcessor

        from llm.governance.gemma_hf_backend import ensure_transformers_gemma4_ready

        self.transformers_version = ensure_transformers_gemma4_ready(auto_install=False)
        self.model_id = model_id
        self.quantization = quantization
        self.max_new_tokens = int(max_new_tokens)
        t0 = time.monotonic()
        self.processor = AutoProcessor.from_pretrained(model_id, token=hf_token)
        kwargs: dict[str, Any] = {"token": hf_token, "device_map": "auto", "dtype": torch.bfloat16}
        if quantization == "4bit":
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                # keep the (unused) vision/audio towers and projectors in bf16
                llm_int8_skip_modules=["vision_tower", "audio_tower", "multi_modal_projector", "embed_vision",
                                       "embed_audio", "lm_head"],
            )
        try:
            from transformers import AutoModelForImageTextToText

            self.model = AutoModelForImageTextToText.from_pretrained(model_id, **kwargs)
        except (ValueError, KeyError):
            self.model = transformers.AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        self.model.eval()
        gc = self.model.generation_config
        for name in ("temperature", "top_p", "top_k"):   # greedy: no sampling knobs left to warn about
            if hasattr(gc, name):
                setattr(gc, name, None)
        cfg = self.model.config
        text_cfg = getattr(cfg, "text_config", None) or cfg
        self.context_tokens = getattr(text_cfg, "max_position_embeddings", None)
        self.load_seconds = round(time.monotonic() - t0, 1)
        logger.success("loaded {} ({}) in {:.0f}s; context {} tokens", model_id, quantization, self.load_seconds,
                       self.context_tokens)

    def _inputs(self, messages: list[dict[str, Any]]) -> Any:
        return self.processor.apply_chat_template(messages, tokenize=True, return_dict=True, return_tensors="pt",
                                                  add_generation_prompt=True, enable_thinking=False)

    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        return int(self._inputs(messages)["input_ids"].shape[-1])

    def generate(self, messages: list[dict[str, Any]]) -> Generation:
        import torch

        inputs = self._inputs(messages)
        input_len = int(inputs["input_ids"].shape[-1])
        if self.context_tokens and input_len + self.max_new_tokens > self.context_tokens:
            raise ContextTooLong(f"the prompt is {input_len:,} tokens; with up to {self.max_new_tokens:,} output "
                                 f"tokens it exceeds {self.model_id}'s context of {self.context_tokens:,}")
        inputs = inputs.to(self.model.device)
        t0 = time.monotonic()
        with torch.inference_mode():
            out = self.model.generate(**inputs, do_sample=False, max_new_tokens=self.max_new_tokens)
        seconds = time.monotonic() - t0
        new = out[0][input_len:]
        text = self.processor.decode(new, skip_special_tokens=True)
        return Generation(text=text.strip(), input_tokens=input_len, output_tokens=int(new.shape[-1]),
                          seconds=seconds, hit_limit=int(new.shape[-1]) >= self.max_new_tokens)


def decoding_settings(generator: Generator) -> dict[str, Any]:
    return {"do_sample": False, "strategy": "greedy", "max_new_tokens": generator.max_new_tokens,
            "enable_thinking": False, "repair_retries": 1}


# ------------------------------------------------------------------------------------------------- one meeting
@dataclass
class Outcome:
    status: str                       # ok | no_items | failed
    text: str | None = None           # the accepted raw answer
    data: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rejected_excerpt: str | None = None

    @property
    def seconds(self) -> float:
        return round(sum(a.get("seconds") or 0.0 for a in self.attempts), 1)

    def tokens(self, key: str) -> int | None:
        vals = [a[key] for a in self.attempts if a.get(key) is not None]
        return sum(vals) if vals else None


RecordCall = Callable[[Generation | None, bool, str | None], None]


def analyze_request(request: dict[str, Any], generator: Generator, *, system_instruction: str = "",
                    record_call: RecordCall | None = None) -> Outcome:
    """Generate, validate, repair once, validate. Never returns ``ok`` for an answer that failed validation."""
    messages = build_messages(request.get("user_message") or "", system_instruction)
    outcome = Outcome(status="failed")
    if not (request.get("user_message") or "").strip():
        outcome.errors = ["the request has no Part 1 message"]
        return outcome
    for attempt in (1, 2):
        try:
            gen = generator.generate(messages)
        except ContextTooLong as exc:
            outcome.errors = [str(exc)]
            if record_call:
                record_call(None, False, "ContextTooLong")
            return outcome
        outcome.attempts.append({"attempt": attempt, "input_tokens": gen.input_tokens,
                                 "output_tokens": gen.output_tokens, "seconds": round(gen.seconds, 1),
                                 "hit_output_limit": gen.hit_limit})
        result = parse_and_validate(gen.text, hit_token_limit=gen.hit_limit)
        if record_call:
            record_call(gen, result.ok, None if result.ok else "SchemaInvalid")
        if result.ok:
            outcome.status = "ok" if result.item_count else "no_items"
            outcome.text, outcome.data, outcome.errors = gen.text, result.data, []
            return outcome
        outcome.errors = result.errors
        outcome.rejected_excerpt = gen.text[:4000]
        logger.warning("attempt {} not valid: {}", attempt, "; ".join(result.errors[:3]))
        messages = repair_messages(messages, gen.text, result)
    return outcome


def meta_payload(request: dict[str, Any], outcome: Outcome, *, generator: Generator, gpu: str, run_date: str,
                 names: dict[str, str], pilot: bool, compute_units: float | None) -> dict[str, Any]:
    """The pipeline's meta keys (``save_transcript_policy_output``) plus how this run made the answer."""
    video = request.get("video") or {}
    prompt_name = request.get("prompt_name") or "policy_analysis_part_1"
    prompt_sha = request.get("prompt_sha256")
    transcript_meta = dict(request.get("transcript_meta") or {})
    transcript_meta.pop("youtube", None)   # the full captions stay in the bundle; keep the meta small
    usage = {
        "input_token_count": outcome.tokens("input_tokens"),
        "output_token_count": outcome.tokens("output_tokens"),
        "thinking_token_count": None,
        "total_token_count": ((outcome.tokens("input_tokens") or 0) + (outcome.tokens("output_tokens") or 0)) or None,
        "latency_seconds": outcome.seconds,
        "attempt_count": len(outcome.attempts),
    }
    return {
        "video_id": video.get("video_id"),
        "video_url": video.get("video_url"),
        "title": video.get("title"),
        "jurisdiction_id": video.get("jurisdiction_id"),
        "prompt_name": prompt_name,
        "prompt_file": f"prompts/{prompt_name}.md",
        "prompt_sha256": prompt_sha,
        "prompt_version": prompt_version_label(prompt_name, prompt_sha),
        # load_analysis_cache_to_bronze reads gemini_model into bronze_events_analysis_ai.ai_model, which dbt carries
        # to event_decision.source_ai_model: it must be the exact model, not a Gemini default.
        "gemini_model": generator.model_id,
        "model": generator.model_id,
        "backend": BACKEND,
        "generation_source": BACKEND,
        "pipeline": PIPELINE,
        "quantization": generator.quantization,
        "gpu_name": gpu,
        "transformers_version": generator.transformers_version,
        "decoding": decoding_settings(generator),
        "generated_at": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "run_date": run_date,
        "pilot": pilot,
        "status": outcome.status,
        "response_chars": len(outcome.text or ""),
        "seconds": outcome.seconds,
        "usage": usage,
        "attempts": outcome.attempts,
        "compute_units": compute_units,
        "compute_units_source": "estimate: GPU seconds x CU/hour" if compute_units is not None else None,
        "json_parsed": outcome.status in ("ok", "no_items"),
        "transcript": transcript_meta,
        "files": {"analysis_json": names["analysis"], "response_txt": names["response"]},
    }


def usage_row(video_id: str, jurisdiction_id: str | None, outcome: Outcome, *, generator: Generator, gpu: str,
              started_ts: str, cu_per_hour: float | None) -> dict[str, Any]:
    """One row per meeting in ``<run>/usage.jsonl``: model, backend, seconds, tokens, status, estimated CU."""
    rate = cu_per_hour if cu_per_hour is not None else COLAB_CU_PER_HOUR.get(gpu.upper())
    cu = estimated_compute_units(outcome.seconds, gpu, cu_per_hour)
    return {
        "platform_name": PLATFORM,
        "step_name": STEP_NAME,
        "row_kind": "meeting",
        "video_id": video_id,
        "jurisdiction_id": jurisdiction_id,
        "model": generator.model_id,
        "backend": BACKEND,
        "quantization": generator.quantization,
        "gpu_name": gpu.upper(),
        "started_ts": started_ts,
        "duration_seconds": outcome.seconds,
        "input_token_count": outcome.tokens("input_tokens"),
        "output_token_count": outcome.tokens("output_tokens"),
        "attempt_count": len(outcome.attempts),
        "run_status_code": outcome.status,
        "compute_units": cu,
        "compute_units_source": (f"estimate: GPU seconds x {rate} CU/hour" if cu is not None
                                 else "unknown: no CU rate for this GPU; read Colab's Resources panel"),
        "cu_per_hour": rate,
        "estimated_cost_usd": None if cu is None else round(cu * COLAB_USD_PER_CU, 6),
        "is_estimated": True,
    }


# ---------------------------------------------------------------------------------------------- run-folder I/O
def _dump(data: Any) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def append_jsonl(store: Store, rel: str, rows: list[dict[str, Any]]) -> None:
    """Append rows (read, add, write: the Files API has no append)."""
    text = store.read_text(rel) or ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += "".join(json.dumps(r, default=str) + "\n" for r in rows)
    store.write_bytes(rel, text.encode("utf-8"))


def read_jsonl(store: Store, rel: str) -> list[dict[str, Any]]:
    rows = []
    for line in (store.read_text(rel) or "").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_comparison(store: Store, run_rel: str, bundle: str, video_id: str, request: dict[str, Any],
                     outcome: Outcome, *, label: str, generator: Generator, gpu: str,
                     compute_units: float | None) -> None:
    """The meeting as an arm of a ``compare_models`` run folder: ``reference.json`` (the Gemini analysis),
    ``transcript.txt``, and ``<arm>.txt`` + ``<arm>.call.json`` (or ``<arm>.failed.json``)."""
    comp = f"{run_rel}/comparison"
    run_json = json.loads(store.read_text(f"{comp}/run.json") or "{}")
    arms = list(run_json.get("arms") or [])
    if label not in arms:
        arms.append(label)
    ids = list(run_json.get("video_ids") or [])
    if video_id not in ids:
        ids.append(video_id)
    run_json.update({"run_id": run_json.get("run_id") or posixpath.basename(run_rel) + "-pilot",
                     "created_at": run_json.get("created_at") or datetime.now(UTC).isoformat(),
                     "reference": "existing", "arms": arms, "video_ids": ids,
                     "jurisdiction_id": run_json.get("jurisdiction_id"),
                     "source": "llm.gpu.colab_policy_analyze --pilot (#511)"})
    store.write_bytes(f"{comp}/run.json", _dump(run_json))
    vdir = f"{comp}/{video_id}"
    ref = store.read_text(f"{bundle}/references/{video_id}.json")
    if ref is not None:
        store.write_bytes(f"{vdir}/reference.json", ref.encode("utf-8"))
    ref_meta = store.read_text(f"{bundle}/references/{video_id}.meta.json")
    if ref_meta is not None:
        store.write_bytes(f"{vdir}/reference.meta.json", ref_meta.encode("utf-8"))
    store.write_bytes(f"{vdir}/transcript.txt", request_transcript(request).encode("utf-8"))
    slug = arm_slug(label)
    record = {
        "arm": label, "model": generator.model_id, "api_mode": BACKEND, "backend": BACKEND,
        "quantization": generator.quantization, "gpu_name": gpu, "video_id": video_id,
        "input_token_count": outcome.tokens("input_tokens"), "cached_input_token_count": None,
        "output_token_count": outcome.tokens("output_tokens"), "thinking_token_count": None,
        "total_token_count": ((outcome.tokens("input_tokens") or 0) + (outcome.tokens("output_tokens") or 0)) or None,
        "latency_seconds": outcome.seconds, "attempt_count": len(outcome.attempts),
        "compute_units": compute_units, "compute_units_source": "estimate: GPU seconds x CU/hour",
        "status": outcome.status, "is_ok": outcome.status in ("ok", "no_items"),
    }
    if record["is_ok"]:
        store.write_bytes(f"{vdir}/{slug}.txt", (outcome.text or "").encode("utf-8"))
        store.write_bytes(f"{vdir}/{slug}.call.json", _dump(record))
    else:
        record["error"] = "; ".join(outcome.errors)[:500]
        store.write_bytes(f"{vdir}/{slug}.failed.json", _dump(record))


# ------------------------------------------------------------------------------------------------------- batch
def run_batch(video_ids: list[str], store: Store, *, bundle: str, out: str, run_date: str,
              generator: Generator | None = None, generator_factory: Callable[[], Generator] | None = None,
              gpu: str = "NONE", cu_per_hour: float | None = None, limit: int | None = DEFAULT_LIMIT,
              pilot: bool = False, secrets: Iterable[str | None] = (), dry_run: bool = False,
              use_gpu_run: bool = True) -> list[dict[str, Any]]:
    """Run the videos not done yet; one summary row per video. Each meeting's files and usage row are written
    before the next starts, so a disconnect loses at most the meeting in progress. Transcript text is never
    logged. The model is loaded only when there's something to run."""
    from llm.usage.calls import LLMCallUsage, llm_call_context, record_llm_call

    secrets = [s for s in secrets if s]
    run_rel = run_dir_rel(out, run_date)
    batch = video_ids[:limit] if limit is not None else list(video_ids)
    todo, done = split_done(batch, store.list_names(run_rel))
    rows: list[dict[str, Any]] = [{"video_id": v, "run_status_code": "skipped"} for v in done]
    for vid in done:
        logger.info("skip {}: analysis already in {} {}", vid, store.label, run_rel)
    if dry_run or not todo:
        for vid in todo:
            present = store.read_text(f"{bundle}/requests/{vid}.json") is not None
            logger.info("would run {} (request {})", vid, "found" if present else "MISSING")
            rows.append({"video_id": vid, "run_status_code": "planned" if present else "missing_request"})
        return rows
    gen = generator or (generator_factory() if generator_factory else None)
    if gen is None:
        raise ValueError("run_batch needs a generator or a generator_factory")
    label = arm_label(gen.model_id, gen.quantization)
    for vid in todo:
        names = output_names(vid)
        started = datetime.now(UTC).isoformat()
        raw = store.read_text(f"{bundle}/requests/{vid}.json")
        if raw is None:
            logger.error("{}: no request in {}/requests/", vid, bundle)
            rows.append({"video_id": vid, "run_status_code": "missing_request"})
            continue
        request = json.loads(raw)
        jid = (request.get("video") or {}).get("jurisdiction_id")

        def record_call(g: Generation | None, ok: bool, err: str | None, _vid: str = vid, _jid: str | None = jid):
            usage = (LLMCallUsage(input_token_count=g.input_tokens, output_token_count=g.output_tokens,
                                  total_token_count=g.input_tokens + g.output_tokens,
                                  latency_seconds=g.seconds, attempt_count=1) if g else LLMCallUsage())
            record_llm_call(provider=BACKEND, model=gen.model_id, usage=usage, is_ok=ok, error_type=err,
                            api_mode=BACKEND, stage="part1", video_id=_vid, jurisdiction_id=_jid)

        try:
            with llm_call_context(stage="part1", video_id=vid, jurisdiction_id=jid, api_mode=BACKEND):
                if use_gpu_run:
                    from llm.usage.gpu import gpu_run

                    with gpu_run(STEP_NAME, device="cuda", video_id=vid, jurisdiction_id=jid):
                        outcome = analyze_request(request, gen, record_call=record_call)
                else:
                    outcome = analyze_request(request, gen, record_call=record_call)
        except Exception as exc:  # noqa: BLE001 - one bad meeting never stops the batch (e.g. CUDA OOM)
            outcome = Outcome(status="failed", errors=[redact(f"{type(exc).__name__}: {str(exc)[:300]}", secrets)])
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
        urow = usage_row(vid, jid, outcome, generator=gen, gpu=gpu, started_ts=started, cu_per_hour=cu_per_hour)
        if outcome.status in ("ok", "no_items"):
            analysis = dict(outcome.data or {})
            if outcome.status == "no_items":
                analysis["_error"] = NO_ITEMS_ERROR   # as the pipeline saves it: kept out of the site
            meta = meta_payload(request, outcome, generator=gen, gpu=gpu, run_date=run_date, names=names,
                                pilot=pilot, compute_units=urow["compute_units"])
            store.write_bytes(f"{run_rel}/{names['response']}", (outcome.text or "").encode("utf-8"))
            store.write_bytes(f"{run_rel}/{names['meta']}", _dump(meta))
            store.write_bytes(f"{run_rel}/{names['analysis']}", _dump(analysis))   # last: it marks the video done
            logger.success("{}: {} in {:.0f}s ({} attempt(s))", vid, outcome.status, outcome.seconds,
                           len(outcome.attempts))
        else:
            store.write_bytes(f"{run_rel}/{names['failed']}", _dump({
                "video_id": vid, "model": gen.model_id, "backend": BACKEND, "quantization": gen.quantization,
                "status": "failed", "errors": outcome.errors, "attempts": outcome.attempts,
                "rejected_excerpt": outcome.rejected_excerpt, "failed_at": datetime.now(UTC).isoformat(),
            }))
            logger.error("{} failed: {}", vid, "; ".join(outcome.errors[:3]))
        append_jsonl(store, f"{run_rel}/usage.jsonl", [urow])
        if pilot:
            write_comparison(store, run_rel, bundle, vid, request, outcome, label=label, generator=gen, gpu=gpu,
                             compute_units=urow["compute_units"])
        rows.append({**urow, "item_count": len((outcome.data or {}).get("decisions") or [])
                     + len((outcome.data or {}).get("uncontested_items") or [])})
    return rows


def write_run_meta(store: Store, run_rel: str, rows: list[dict[str, Any]], *, generator: Generator, gpu: str,
                   bundle: str, pilot: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """The run-level ``meta.json``: model, precision, GPU, versions, decoding and the outcome counts."""
    manifest = json.loads(store.read_text(f"{bundle}/manifest.json") or "{}")
    prior = json.loads(store.read_text(f"{run_rel}/meta.json") or "{}")
    sessions = list(prior.get("sessions") or [])
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("run_status_code", "?")] = counts.get(r.get("run_status_code", "?"), 0) + 1
    sessions.append({
        "ended_at": datetime.now(UTC).isoformat(), "model": generator.model_id, "backend": BACKEND,
        "quantization": generator.quantization, "gpu_name": gpu, "transformers_version":
        generator.transformers_version, "decoding": decoding_settings(generator), "pilot": pilot,
        "counts": counts, "gpu_seconds": round(sum(r.get("duration_seconds") or 0 for r in rows
                                                   if r.get("run_status_code") not in ("skipped", "planned")), 1),
        **(extra or {}),
    })
    meta = {"bundle": bundle, "prompt_name": manifest.get("prompt_name"),
            "prompt_sha256": manifest.get("prompt_sha256"), "prompt_version": manifest.get("prompt_version"),
            "sessions": sessions}
    store.write_bytes(f"{run_rel}/meta.json", _dump(meta))
    return meta


def record_measured_cu(store: Store, out: str, run_date: str, balance_before: float | None,
                       balance_after: float | None, gpu: str, started_after: str | None = None) -> dict | None:
    """Append the batch's measured CU (balance before minus after) to ``usage.jsonl`` and apportion it to the
    meetings run in this session (``started_after``, else all) by GPU seconds, labelled an estimate. Pilot
    comparison records get their meeting's share as ``compute_units``."""
    used = measured_batch_cu(balance_before, balance_after)
    if used is None:
        return None
    run_rel = run_dir_rel(out, run_date)
    rows = [r for r in read_jsonl(store, f"{run_rel}/usage.jsonl") if r.get("row_kind") == "meeting"
            and (started_after is None or str(r.get("started_ts") or "") >= started_after)]
    shares = apportion(used, {r["video_id"]: r.get("duration_seconds") or 0 for r in rows})
    now = datetime.now(UTC).isoformat()
    batch = {"platform_name": PLATFORM, "step_name": STEP_NAME, "row_kind": "batch_measured_cu",
             "gpu_name": gpu.upper(), "recorded_ts": now, "cu_balance_before": float(balance_before),
             "cu_balance_after": float(balance_after), "compute_units": used, "meeting_count": len(shares),
             "compute_units_source": "measured: Colab Resources panel balance before minus after",
             "is_estimated": False}
    per = [{"platform_name": PLATFORM, "step_name": STEP_NAME, "row_kind": "meeting_apportioned_cu",
            "video_id": vid, "gpu_name": gpu.upper(), "recorded_ts": now, "compute_units": cu,
            "estimated_cost_usd": round(cu * COLAB_USD_PER_CU, 6),
            "compute_units_source": "estimate: measured batch CU apportioned by GPU seconds",
            "is_estimated": True} for vid, cu in shares.items()]
    append_jsonl(store, f"{run_rel}/usage.jsonl", [batch, *per])
    comp = f"{run_rel}/comparison"
    run_json = json.loads(store.read_text(f"{comp}/run.json") or "{}")
    for vid, cu in shares.items():
        for label in run_json.get("arms") or []:
            rel = f"{comp}/{vid}/{arm_slug(label)}.call.json"
            text = store.read_text(rel)
            if text is None:
                continue
            rec = json.loads(text)
            if rec.get("backend") == BACKEND:
                rec.update({"compute_units": cu,
                            "compute_units_source": "estimate: measured batch CU apportioned by GPU seconds"})
                store.write_bytes(rel, _dump(rec))
    return batch


def copy_gpu_run_rows(store: Store, run_rel: str, session_tag: str) -> None:
    """Copy this session's ``llm.usage`` rows (``gpu_runs_*``, ``llm_calls_*``) to ``<run>/llm_usage/``."""
    from llm.usage.calls import usage_log_dir

    for pattern in ("gpu_runs_*.jsonl", "llm_calls_*.jsonl"):
        for path in sorted(usage_log_dir().glob(pattern)):
            store.write_bytes(f"{run_rel}/llm_usage/{path.stem}_{session_tag}.jsonl", path.read_bytes())


def summary_table(rows: list[dict[str, Any]]) -> str:
    head = ("video_id", "status", "items", "in_tokens", "out_tokens", "attempts", "seconds", "cu (estimate)")
    lines = [head]
    for r in rows:
        lines.append((str(r.get("video_id", "")), str(r.get("run_status_code", "")),
                      "" if r.get("item_count") is None else str(r["item_count"]),
                      "" if r.get("input_token_count") is None else f"{r['input_token_count']:,}",
                      "" if r.get("output_token_count") is None else f"{r['output_token_count']:,}",
                      "" if r.get("attempt_count") is None else str(r["attempt_count"]),
                      "" if r.get("duration_seconds") is None else f"{r['duration_seconds']:.0f}",
                      "" if r.get("compute_units") is None else f"{r['compute_units']:.3f}"))
    widths = [max(len(line[i]) for line in lines) for i in range(len(head))]
    out = ["  ".join(c.ljust(w) for c, w in zip(line, widths)) for line in lines]
    ran = [r for r in rows if r.get("duration_seconds") is not None]
    ok = sum(r.get("run_status_code") in ("ok", "no_items") for r in ran)
    cus = [r["compute_units"] for r in ran if r.get("compute_units") is not None]
    out.append(f"{ok}/{len(ran)} valid; {sum(r['duration_seconds'] for r in ran):.0f} GPU seconds; "
               f"~{sum(cus):.3f} CU (estimate)")
    return "\n".join(out)


# --------------------------------------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m llm.gpu.colab_policy_analyze",
                                description="Part 1 policy analysis with Gemma 4 on a Colab GPU (#511).")
    p.add_argument("--videos-file", required=True,
                   help="videos.txt in an exported bundle, relative to the landing volume / Drive folder "
                        "(e.g. policy_export/2026-11-17/videos.txt)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Hugging Face model or alias (default {DEFAULT_MODEL}; faster: gemma-4-26b-a4b-it)")
    p.add_argument("--quantize", choices=("auto", "4bit", "none"), default="auto",
                   help="auto: 4-bit under 70 GB of GPU memory, else bf16")
    p.add_argument("--pilot", type=int, default=0,
                   help="run N meetings from pilot_videos.txt (already analyzed by Gemini) and write a "
                        "compare_models arm")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"most meetings this run (default {DEFAULT_LIMIT})")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"results root in the volume / Drive folder (default {DEFAULT_OUT})")
    p.add_argument("--run-date", default=None, help="run folder date, YYYY-MM-DD (default today, UTC); reuse it to "
                   "resume an earlier run")
    p.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    p.add_argument("--volume", default=LANDING_VOLUME)
    p.add_argument("--drive-root", default=DRIVE_ROOT, help="folder used when no Databricks credentials are set")
    p.add_argument("--cu-per-hour", type=float, default=None, help="CU/hour from Colab's Resources panel")
    p.add_argument("--dry-run", action="store_true", help="plan and show skips; no model, no writes")
    return p


def main(argv: list[str] | None = None, *, store: Store | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_date = check_run_date(args.run_date or today_utc())
    model_id = resolve_model(args.model)
    secrets = [get_secret(n) for n in TOKEN_NAMES]
    hf_token = get_secret("HF_TOKEN")
    store = store or make_store(args.volume, args.drive_root)
    bundle = bundle_rel(args.videos_file)
    if args.pilot:
        ids = read_ids(store.read_text(f"{bundle}/pilot_videos.txt"))[: args.pilot]
        if not ids:
            logger.error("--pilot needs {}/pilot_videos.txt (export with --pilot N)", bundle)
            return 2
    else:
        ids = read_ids(store.read_text(clean_rel(args.videos_file)))
        if not ids:
            logger.error("no video ids in {}", args.videos_file)
            return 2
    gpu, mem_gb = "NONE", None
    if not args.dry_run:
        from llm.gpu.colab_io import gpu_memory_gb
        from llm.usage.gpu import gpu_names

        names = gpu_names()
        if not names:
            logger.error("No GPU attached. Colab: Runtime > Change runtime type > A100 (or L4) GPU.")
            return 2
        gpu, mem_gb = gpu_kind(names[0]), gpu_memory_gb()
        if not hf_token:
            logger.error("No HF_TOKEN in Colab secrets or the environment (the Gemma 4 weights are gated).")
            return 2
    quant = choose_quantization(args.quantize, mem_gb)
    run_rel = run_dir_rel(args.out, run_date)
    logger.info("run {}: {} meetings, {} ({}) on {} ({} GB); results to {} {}", run_date, len(ids), model_id, quant,
                gpu, mem_gb, store.label, run_rel)
    holder: dict[str, Any] = {}

    def factory() -> Generator:
        holder["gen"] = HFGemmaGenerator(model_id, quant, max_new_tokens=args.max_new_tokens, hf_token=hf_token)
        return holder["gen"]

    rows = run_batch(ids, store, bundle=bundle, out=args.out, run_date=run_date, generator_factory=factory,
                     gpu=gpu, cu_per_hour=args.cu_per_hour, limit=args.limit, pilot=bool(args.pilot),
                     secrets=secrets, dry_run=args.dry_run)
    gen = holder.get("gen")
    if gen is not None:
        write_run_meta(store, run_rel, rows, generator=gen, gpu=gpu, bundle=bundle, pilot=bool(args.pilot),
                       extra={"load_seconds": getattr(gen, "load_seconds", None), "gpu_memory_gb": mem_gb})
        try:
            copy_gpu_run_rows(store, run_rel, datetime.now(UTC).strftime("%H%M%S"))
        except Exception as exc:  # noqa: BLE001 - usage copy never fails the run
            logger.warning("usage rows not copied: {}", redact(str(exc), secrets))
    print(summary_table(rows))
    if args.pilot and gen is not None:
        print(f"pilot comparison: {store.label} {run_rel}/comparison  ->  python -m llm.gemini.compare_models "
              f"--rescore <that folder>")
    ran = [r for r in rows if r.get("run_status_code") in ("ok", "no_items", "failed")]
    return 1 if ran and all(r["run_status_code"] == "failed" for r in ran) else 0


if __name__ == "__main__":
    sys.exit(main())
