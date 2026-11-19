"""CLI: propose NER person/place candidates from a transcript (#623).

Example::

    python -m llm.ner.transcript_candidates \\
        --transcript path/to.txt --video-id Vs1PKup62NA \\
        --out /path/on/Drive/crawl/.../ner_candidates.json

With ``--jev-confirm``, each person candidate is scored with Jev (needs
``JEV_API_KEY`` or ``TYPESAFE_API_KEY``). Deliverables belong on Google Drive
under ``CommunityOne/open-navigator/crawl/``, not Downloads (``AGENTS.md``).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from llm.ner.candidates import extract_candidates, jev_confirm_people


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--transcript", type=Path, required=True, help="Transcript text file")
    p.add_argument("--video-id", default="", help="YouTube video id for the payload")
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="JSON path (prefer CommunityOne/open-navigator/crawl/... on Drive)",
    )
    p.add_argument("--model", default="en_core_web_sm", help="spaCy model name")
    p.add_argument(
        "--jev-confirm",
        action="store_true",
        help="Confirm PERSON candidates with Jev Noul",
    )
    p.add_argument("--jev-threshold", type=float, default=0.5)
    return p


def _api_key() -> str:
    return (
        os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY") or ""
    ).strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = args.transcript.read_text(encoding="utf-8")
    if "=== TRANSCRIPT ===" in text:
        text = text.split("=== TRANSCRIPT ===", 1)[-1].strip()

    candidates = extract_candidates(text, model=args.model)
    people = [c for c in candidates if c.label == "PERSON"]
    places = [c for c in candidates if c.label == "PLACE"]

    payload: dict = {
        "video_id": args.video_id or None,
        "source_system": "spacy_ner",
        "spacy_model": args.model,
        "generated_at": datetime.now(UTC).isoformat(),
        "transcript_chars": len(text),
        "people": [c.to_dict() for c in people],
        "places": [c.to_dict() for c in places],
        "next_steps": [
            "Load into bronze (bronze_persons_from_ner) when the table exists (#623)",
            "Run ingestion.mdm Splink person linking — do not invent a second MDM tool",
            "Jev roster screen can use MDM + these candidates",
        ],
    }

    if args.jev_confirm:
        key = _api_key()
        if not key:
            raise SystemExit("Set JEV_API_KEY or TYPESAFE_API_KEY for --jev-confirm")
        from llm.typesafe.client import JevClient
        from llm.usage.calls import llm_call_context

        with llm_call_context(
            stage="jev_ner_confirm", video_id=args.video_id or None
        ), JevClient(api_key=key) as client:
            confirmed = jev_confirm_people(
                text, people, client=client, threshold=args.jev_threshold
            )
        payload["people_jev"] = confirmed
        payload["people_jev_present"] = [
            r for r in confirmed if r.get("jev_present")
        ]
        logger.info(
            "Jev kept {}/{} person candidates",
            len(payload["people_jev_present"]),
            len(confirmed),
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.success("Wrote {} ({} people, {} places)", args.out, len(people), len(places))
    if "Downloads" in str(args.out).replace("\\", "/"):
        logger.warning(
            "Output looks like Downloads — AGENTS.md says use "
            "CommunityOne/open-navigator/crawl/ on Google Drive"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
