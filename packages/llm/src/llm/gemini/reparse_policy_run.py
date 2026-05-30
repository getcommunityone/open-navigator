#!/usr/bin/env python3
"""Re-extract analysis.json / report.md from a saved Gemini browser scrape."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.gemini.browser_policy_analysis import (  # noqa: E402
    _REPO_ROOT as REPO,
    _normalize_part1_analysis,
    _part1_json_ok,
    _split_gemini_documents,
    _warn_if_sparse_decisions,
    _write_diagrams_md,
    _write_diagrams_from_raw,
)


def _stem_from_analysis_path(analysis_path: Path) -> str:
    name = analysis_path.name
    if not name.endswith("_analysis.json"):
        raise ValueError(f"Expected *_analysis.json, got {analysis_path}")
    return name[: -len("_analysis.json")]


def normalize_analysis_file(analysis_path: Path) -> bool:
    """Split legacy procedural_light rows into uncontested_items[] (no Gemini)."""
    from scripts.gemini.browser_policy_analysis import _normalize_part1_analysis

    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    if data.get("_error"):
        print("Cannot normalize error stub", file=sys.stderr)
        return False
    norm = _normalize_part1_analysis(data)
    analysis_path.write_text(
        json.dumps(norm, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Normalized {analysis_path.name}: "
        f"{len(norm.get('decisions') or [])} contested, "
        f"{len(norm.get('uncontested_items') or [])} uncontested"
    )
    return True


def reparse_run(
    analysis_path: Path,
    *,
    raw_path: Path | None = None,
    write_report: bool = True,
) -> bool:
    folder = analysis_path.parent
    stem = _stem_from_analysis_path(analysis_path)
    raw_path = raw_path or folder / f"{stem}_response_raw.md"
    if not raw_path.is_file():
        print(f"No raw scrape at {raw_path}", file=sys.stderr)
        return False

    text = raw_path.read_text(encoding="utf-8")
    parsed, markdown_docs = _split_gemini_documents(text)
    if not _part1_json_ok(parsed):
        print("Could not parse meeting JSON from raw scrape", file=sys.stderr)
        return False
    parsed = _normalize_part1_analysis(parsed)

    analysis_path.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _warn_if_sparse_decisions(
        parsed,
        video_id=str(parsed.get("meeting", {}).get("meeting_id", stem)),
        prompt_name=stem,
    )

    if write_report:
        report_path = folder / f"{stem}_report.md"
        report_body = markdown_docs[0] if markdown_docs else ""
        if report_body:
            report_path.write_text(report_body + "\n", encoding="utf-8")
        diagrams_path = folder / f"{stem}_diagrams.md"
        _write_diagrams_md(parsed, diagrams_path) or _write_diagrams_from_raw(
            text, diagrams_path
        )

    meta_path = folder / f"{stem}_meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["json_parsed"] = True
        meta["response_chars"] = len(text)
        meta["report_chars"] = len(markdown_docs[0]) if markdown_docs else 0
        files = meta.get("files") or {}
        files["analysis_json"] = str(analysis_path.relative_to(REPO))
        files["response_raw_md"] = str(raw_path.relative_to(REPO))
        meta["files"] = files
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {analysis_path}")
    return True


def scrape_gemini_last_reply(
    *,
    user_data_dir: Path,
    profile_name: str,
    gemini_url: str,
    headless: bool,
) -> str | None:
    from playwright.sync_api import sync_playwright

    from scripts.gemini.browser_policy_analysis import (
        DEFAULT_GEMINI_URL,
        _extract_broad_model_reply_js,
        _extract_model_response_js,
        _navigate_to_gemini,
        _open_page,
    )

    with sync_playwright() as p:
        page, handle, mode, should_close = _open_page(
            p,
            user_data_dir=user_data_dir,
            profile_name=profile_name,
            headless=headless,
            cdp_url=None,
            fresh_profile=False,
        )
        try:
            _navigate_to_gemini(
                page, gemini_url or DEFAULT_GEMINI_URL, timeout_ms=120_000
            )
            text = (
                _extract_model_response_js(page, min_chars=500)
                or _extract_broad_model_reply_js(page, min_chars=500)
                or ""
            ).strip()
            return text or None
        finally:
            if should_close:
                handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "analysis_json",
        type=Path,
        help="Path to *_analysis.json (error stub or existing)",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help="Override path to *_response_raw.md",
    )
    parser.add_argument(
        "--normalize-only",
        action="store_true",
        help="Rewrite analysis.json: move procedural_light decisions[] → uncontested_items[]",
    )
    parser.add_argument(
        "--scrape-gemini",
        action="store_true",
        help="Fetch latest model reply from persisted Gemini profile and save as raw",
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=REPO / "data/cache/gemini_browser_chrome_profile",
    )
    parser.add_argument("--profile-name", default="Default")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    analysis_path = args.analysis_json.resolve()

    if args.normalize_only:
        return 0 if normalize_analysis_file(analysis_path) else 1

    stem = _stem_from_analysis_path(analysis_path)
    raw_path = args.raw or analysis_path.parent / f"{stem}_response_raw.md"

    if args.scrape_gemini:
        text = scrape_gemini_last_reply(
            user_data_dir=args.user_data_dir,
            profile_name=args.profile_name,
            gemini_url="https://gemini.google.com/app",
            headless=args.headless,
        )
        if not text:
            print("No model reply found in Gemini UI", file=sys.stderr)
            return 1
        raw_path.write_text(text + "\n", encoding="utf-8")
        print(f"Saved raw scrape ({len(text)} chars) → {raw_path}")

    return 0 if reparse_run(analysis_path, raw_path=raw_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
