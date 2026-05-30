"""
ShieldGemma-style safety review of pipeline LLM outputs.

Writes per-artifact ``.shield.json`` files and ``05_safety_review/_summary.json``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .governance_meeting_llm import shield_review_text


def safety_review_enabled() -> bool:
    return os.environ.get("GOVERNANCE_SAFETY_REVIEW", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _max_review_files() -> int:
    try:
        return max(1, int(os.environ.get("GOVERNANCE_SHIELD_MAX_FILES", "40")))
    except ValueError:
        return 40


# Stable step ids (glob keys) → judge-facing descriptions for _summary.json.
REVIEW_STEP_DESCRIPTIONS: Dict[str, str] = {
    "demo1_ocr": "Demo 1 — visual OCR on scanned PDF (dark-data recovery)",
    "demo2_page": "Demo 2 — per-page extract with visual token budget (HIGH/LOW)",
    "demo3_thinking": "Demo 3 — policy analysis JSON (thinking mode)",
    "demo3_thinking_raw": "Demo 3 — policy analysis raw model output",
    "demo3_summary": "Demo 3 — human-readable thinking summary (markdown)",
    "demo4_chunk": "Demo 4 — long-meeting audio chunk policy JSON",
    "demo4_drift": "Demo 4 — policy drift detector across chunks",
    "demo5_image": "Demo 5 — contact / collateral image triage JSON",
}


@dataclass(frozen=True)
class _ReviewTarget:
    step_id: str
    label: str
    path: Path
    text: str


def describe_review_step(step_id: str, path: Path) -> str:
    """Human-readable label; adds page number for Demo 2 page artifacts."""
    base = REVIEW_STEP_DESCRIPTIONS.get(
        step_id, f"Pipeline output ({step_id.replace('_', ' ')})"
    )
    if step_id == "demo2_page":
        m = re.search(r"page_(\d+)", path.name, re.IGNORECASE)
        if m:
            return f"{base} — page {int(m.group(1))}"
    return base


def _load_json_text(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return json.dumps(data, ensure_ascii=False)


def _load_plain_text(path: Path, *, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:limit]


def collect_review_targets(
    gemma_json_root: Path,
    *,
    summaries_root: Optional[Path] = None,
    max_files: Optional[int] = None,
) -> List[_ReviewTarget]:
    """
    Discover LLM outputs to review (fixed globs — ``chunk_000.json`` not ``*.chunk_*.json``).
    """
    root = gemma_json_root.resolve()
    if not root.is_dir():
        return []

    cap = max_files if max_files is not None else _max_review_files()
    specs: List[Tuple[str, str, str]] = [
        ("demo4_chunk", "chunk_*.json", "json"),
        ("demo4_drift", "policy_drift.json", "json"),
        ("demo3_thinking", "*.thinking.json", "json"),
        ("demo3_thinking_raw", "*.thinking.raw.txt", "text"),
        ("demo5_image", "*.image_triage.json", "json"),
        ("demo1_ocr", "*.visual_ocr.txt", "text"),
        ("demo2_page", "page_*.json", "json"),
    ]

    targets: List[_ReviewTarget] = []
    seen: set[str] = set()

    for step_id, pattern, kind in specs:
        for path in sorted(root.rglob(pattern)):
            key = str(path.resolve())
            if key in seen:
                continue
            if not path.is_file():
                continue
            if kind == "json":
                text = _load_json_text(path)
            else:
                text = _load_plain_text(path)
            if not text.strip():
                continue
            seen.add(key)
            targets.append(
                _ReviewTarget(
                    step_id=step_id,
                    label=describe_review_step(step_id, path),
                    path=path,
                    text=text,
                )
            )
            if len(targets) >= cap:
                return targets

    if summaries_root:
        sroot = summaries_root.resolve()
        if sroot.is_dir():
            for path in sorted(sroot.rglob("*.thinking.summary.md")):
                key = str(path.resolve())
                if key in seen or not path.is_file():
                    continue
                text = _load_plain_text(path)
                if not text.strip():
                    continue
                seen.add(key)
                targets.append(
                    _ReviewTarget(
                        step_id="demo3_summary",
                        label=describe_review_step("demo3_summary", path),
                        path=path,
                        text=text,
                    )
                )
                if len(targets) >= cap:
                    break

    return targets


def run_safety_review(
    *,
    api_key: str,
    shield_model: str,
    gemma_json_root: Path,
    safety_root: Path,
    summaries_root: Optional[Path] = None,
    max_files: Optional[int] = None,
) -> Dict[str, Any]:
    """Review pipeline outputs; return summary dict (also written to ``_summary.json``)."""
    safety_root = safety_root.resolve()
    safety_root.mkdir(parents=True, exist_ok=True)
    gemma_json_root = gemma_json_root.resolve()

    targets = collect_review_targets(
        gemma_json_root, summaries_root=summaries_root, max_files=max_files
    )

    reviewed: List[Dict[str, Any]] = []
    flagged_count = 0

    if not api_key:
        summary = {
            "model": shield_model,
            "reviewed_count": 0,
            "flagged_count": 0,
            "reviewed": [],
            "skipped": "missing GEMINI_API_KEY",
        }
        (safety_root / "_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("Safety review skipped: set GEMINI_API_KEY for ShieldGemma.")
        return summary

    if not targets:
        summary = {
            "model": shield_model,
            "reviewed_count": 0,
            "flagged_count": 0,
            "reviewed": [],
            "skipped": "no outputs found under gemma_json_root",
            "gemma_json_root": str(gemma_json_root),
        }
        (safety_root / "_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            "Safety review: no LLM outputs found yet "
            f"(searched {gemma_json_root}). Run §6 pipeline first."
        )
        return summary

    print(f"Safety review | {len(targets)} file(s) | model={shield_model}")

    for target in targets:
        try:
            result = shield_review_text(
                api_key=api_key,
                model=shield_model,
                content=target.text[:4000],
                user_prompt=f"(automated {target.label} from open-navigator pipeline)",
            )
        except Exception as exc:
            print(f"  ! shield failed | {target.path.name}: {exc}")
            continue

        try:
            rel = target.path.resolve().relative_to(gemma_json_root)
        except ValueError:
            rel = Path(target.path.name)

        out = safety_root / rel.with_suffix(".shield.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        entry = {
            "source": str(rel),
            "step_id": target.step_id,
            "label": target.label,
            "flagged": result["flagged"],
            "categories": result["categories"],
        }
        reviewed.append(entry)
        if result["flagged"]:
            flagged_count += 1
            print(f"  ⚠ flagged | {rel} — {result.get('rationale', '')}")

    summary = {
        "model": shield_model,
        "reviewed_count": len(reviewed),
        "flagged_count": flagged_count,
        "reviewed": reviewed,
    }
    (safety_root / "_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"ShieldGemma review done — {len(reviewed)} reviewed, {flagged_count} flagged "
        f"→ {safety_root / '_summary.json'}"
    )
    return summary
