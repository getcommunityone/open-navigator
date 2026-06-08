#!/usr/bin/env python3
"""
Meeting-document enrichment — bring AGENDA / MINUTES detail into the analysis.

The policy-analysis JSON today is 100% transcript-derived. Agendas and minutes
(already scraped to disk) carry authoritative detail transcripts lack: agenda
item numbers, exact motions (moved/seconded), recorded votes, official outcomes
incl. continuances + continued-to dates, and ordinance/resolution numbers. This
module is the follow-up enrichment task that will extract that detail and MERGE
it into each meeting's analysis JSON.

Stages
------
1. INDEX   (free)  — discover candidate agenda/minutes docs across formats.
2. MATCH   (free)  — link each doc to an analyzed meeting by jurisdiction + date.
3. EXTRACT (BILLED)— Gemini reads each doc and returns official structure.
4. MERGE   (free)  — write the structure back into the meeting analysis JSON.

ONLY stage 1 (INDEX, free) is implemented here. Stages 2-4 (MATCH to a meeting,
EXTRACT via Gemini, MERGE into the analysis JSON) are scaffolded with the
contract documented; extraction is opt-in and scoped so a billed Gemini run can
never happen by accident (keys are BILLED — a prior full-US run cost ~$22).

Documents live on disk under
``data/cache/scraped_meetings/<ST>/<segment>/<jid>/`` — indexed per jurisdiction
in ``_manifest.json`` (key ``pdfs[]``, a MIXED-document list: pdf/docx/doc/ashx),
plus HTML agendas saved as CivicPlus pages under ``_crawl_html/page__*.html``.

Usage::

    # FREE: discover + report coverage (default)
    python -m llm.gemini.meeting_document_enrichment
    python -m llm.gemini.meeting_document_enrichment --jurisdiction hampshire_25015

    # BILLED (opt-in, scoped — not implemented yet):
    python -m llm.gemini.meeting_document_enrichment --extract --jurisdiction <id> --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from loguru import logger

# Repo root (…/open-navigator) — five parents up from this module file.
PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCRAPE_ROOT = PROJECT_ROOT / "data" / "cache" / "scraped_meetings"

# doc_type values (in manifest pdfs[]) we treat as agenda/minutes content.
AGENDA_MINUTES_DOC_TYPES = {"agenda", "minutes", "agenda_packet", "packet"}
# Extensions we can normalize for extraction (audio/video are skipped).
SUPPORTED_EXTS = {"pdf", "docx", "doc", "html", "htm", "ashx"}
# HTML page filenames (CivicPlus AgendaCenter / DocumentCenter) that are agendas
# or minutes. These are NOT in pdfs[]; they're scraped pages under _crawl_html/.
_HTML_DOC_RE = re.compile(r"(agenda|minute|documentcenter)", re.IGNORECASE)

# Date patterns seen in anchor_text / filenames: 3.12.26, 04072026, 2026-03-12,
# 03/12/2026, March 12 2026. Best-effort — MATCH stays conservative.
_DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[-_/.](?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})"),       # 2026-03-12
    re.compile(r"(?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})[-_/.](?P<y>20\d{2})"),       # 03/12/2026
    re.compile(r"(?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})[-_/.](?P<yy>\d{2})\b"),      # 3.12.26
    re.compile(r"\b(?P<m>\d{2})(?P<d>\d{2})(?P<y>20\d{2})\b"),                   # 04072026
]


@dataclass
class DocCandidate:
    """One agenda/minutes document found on disk, before any extraction."""

    jurisdiction_id: str
    state: Optional[str]
    segment: Optional[str]              # municipality | county | school
    doc_type: str                       # agenda | minutes | agenda_packet | packet
    fmt: str                            # pdf | docx | doc | html | ashx
    local_path: Optional[str]
    url: Optional[str]
    iso_date: Optional[str] = None      # best-effort YYYY-MM-DD, may be None
    anchor_text: Optional[str] = None
    civicclerk_event_id: Optional[str] = None


def _parse_iso_date(*texts: Optional[str]) -> Optional[str]:
    """Best-effort YYYY-MM-DD from anchor text / filename / url. None if unsure."""
    for text in texts:
        if not text:
            continue
        for pat in _DATE_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            gd = m.groupdict()
            year = gd.get("y") or (("20" + gd["yy"]) if gd.get("yy") else None)
            if not year:
                continue
            try:
                mm, dd = int(gd["m"]), int(gd["d"])
                if 1 <= mm <= 12 and 1 <= dd <= 31:
                    return f"{int(year):04d}-{mm:02d}-{dd:02d}"
            except (KeyError, ValueError):
                continue
    return None


def _ext_of(path_or_url: Optional[str]) -> str:
    if not path_or_url:
        return "?"
    tail = path_or_url.split("?")[0].rsplit(".", 1)
    return tail[-1].lower() if len(tail) == 2 else "?"


def _segment_state_jid(manifest_path: Path) -> tuple[Optional[str], Optional[str], str]:
    """From …/scraped_meetings/<ST>/<segment>/<jid>/_manifest.json -> (state, segment, jid)."""
    parts = manifest_path.relative_to(SCRAPE_ROOT).parts
    state = parts[0] if len(parts) >= 1 else None
    segment = parts[1] if len(parts) >= 2 else None
    jid = parts[2] if len(parts) >= 3 else manifest_path.parent.name
    return state, segment, jid


def _index_manifest(manifest_path: Path) -> Iterable[DocCandidate]:
    """Yield agenda/minutes candidates from a jurisdiction manifest + its HTML pages."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("Skipping unreadable manifest {}: {}", manifest_path, exc)
        return

    state, segment, jid = _segment_state_jid(manifest_path)
    jurisdiction_id = manifest.get("jurisdiction_id") or jid

    # (a) pdfs[] — mixed-document list (pdf/docx/doc/ashx) with doc_type.
    for entry in manifest.get("pdfs") or []:
        doc_type = (entry.get("doc_type") or "").lower()
        if doc_type not in AGENDA_MINUTES_DOC_TYPES:
            continue
        fmt = _ext_of(entry.get("path") or entry.get("url"))
        if fmt not in SUPPORTED_EXTS:
            continue  # audio/video/etc. mislabeled — skip
        anchor = entry.get("anchor_text")
        yield DocCandidate(
            jurisdiction_id=jurisdiction_id,
            state=state,
            segment=segment,
            doc_type=doc_type,
            fmt=fmt,
            local_path=entry.get("path"),
            url=entry.get("url"),
            iso_date=_parse_iso_date(anchor, entry.get("url"), entry.get("path")),
            anchor_text=anchor,
            civicclerk_event_id=entry.get("civicclerk_event_id"),
        )

    # (b) HTML agendas/minutes — CivicPlus pages under _crawl_html/.
    html_dir = manifest_path.parent / "_crawl_html"
    if html_dir.is_dir():
        for page in html_dir.glob("page__*.htm*"):
            if not _HTML_DOC_RE.search(page.name):
                continue
            doc_type = "minutes" if "minute" in page.name.lower() else "agenda"
            yield DocCandidate(
                jurisdiction_id=jurisdiction_id,
                state=state,
                segment=segment,
                doc_type=doc_type,
                fmt="html",
                local_path=str(page),
                url=None,
                iso_date=_parse_iso_date(page.name),
                anchor_text=page.name,
            )


def index_all(jurisdiction: Optional[str] = None) -> list[DocCandidate]:
    """Walk every manifest and return all agenda/minutes candidates."""
    out: list[DocCandidate] = []
    for mp in sorted(SCRAPE_ROOT.glob("*/*/*/_manifest.json")):
        out.extend(_index_manifest(mp))
    if jurisdiction:
        # Match on the manifest's jurisdiction_id (what we report) or the on-disk
        # path — the directory slug and the manifest id don't always coincide.
        out = [
            c for c in out
            if jurisdiction in (c.jurisdiction_id or "") or jurisdiction in (c.local_path or "")
        ]
    return out


def _report(candidates: list[DocCandidate]) -> None:
    from collections import Counter

    by_fmt = Counter(c.fmt for c in candidates)
    by_type = Counter(c.doc_type for c in candidates)
    dated = sum(1 for c in candidates if c.iso_date)
    juris = len({c.jurisdiction_id for c in candidates})
    logger.success("Indexed {} agenda/minutes docs across {} jurisdictions", len(candidates), juris)
    logger.info("  by format: {}", dict(by_fmt.most_common()))
    logger.info("  by doc_type: {}", dict(by_type.most_common()))
    logger.info("  with a parsed date: {}/{}", dated, len(candidates))
    for c in candidates[:6]:
        logger.info(
            "  e.g. {} | {} | {} | {} | {}",
            c.jurisdiction_id, c.doc_type, c.fmt, c.iso_date or "no-date",
            (c.anchor_text or c.url or c.local_path or "")[:60],
        )


# ---------------------------------------------------------------------------
# Stages 3-4 — EXTRACT (Gemini, BILLED) + MERGE — scaffolded, NOT implemented.
# Contract for the follow-up:
#   normalize(candidate) -> text|pdf bytes:
#       pdf  -> Gemini native (or pdfplumber text)
#       docx -> python-docx text
#       doc  -> libreoffice --headless convert (or antiword); else skip+warn
#       html -> readability/selectolax text strip (drop CivicPlus nav)
#       ashx -> sniff content-type, route to pdf/doc handler
#   extract(text, doc_type) -> dict via a FOCUSED agenda/minutes Gemini prompt:
#       { agenda_items: [{item_number, title, disposition}],
#         motions: [{moved_by, seconded_by, on_item}],
#         recorded_votes: [{item, yes, no, abstain, result}],
#         official_outcomes: [{item, outcome, continued_to_date}],
#         legislation_numbers: [...] }
#   merge(analysis_json, extracted): add a top-level `meeting_documents` block and,
#       where an agenda item confidently maps to a decisions[]/uncontested_items[]
#       row (by item number / subject / place), add official_* fields WITHOUT
#       overwriting transcript-derived fields. Re-stamp; re-persist via
#       llm.gemini.persist_policy_analysis_bronze. Match the analysis cache layout
#       in llm.gemini.meeting_transcript_policy (jurisdiction_root / iter_analysis_files).
# ---------------------------------------------------------------------------
def _extract_and_merge_guard(args: argparse.Namespace) -> int:
    if not (args.jurisdiction and args.limit):
        logger.error(
            "--extract requires --jurisdiction <id> AND --limit N (billed Gemini; "
            "scoped runs only — never all jurisdictions at once)."
        )
        return 2
    logger.error(
        "EXTRACT/MERGE not implemented yet — the free INDEX stage is wired; the "
        "Gemini extraction + JSON merge are the documented follow-up (see module "
        "docstring). Refusing to proceed so no billed call happens by accident."
    )
    return 3


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jurisdiction", help="Limit to a jurisdiction_id substring (e.g. hampshire_25015)")
    parser.add_argument("--extract", action="store_true", help="(BILLED, opt-in) run Gemini extraction — requires --jurisdiction + --limit")
    parser.add_argument("--limit", type=int, default=0, help="Max meetings to extract in one run (extraction only)")
    args = parser.parse_args(argv)

    if not SCRAPE_ROOT.is_dir():
        logger.error("Scrape cache not found: {}", SCRAPE_ROOT)
        return 1

    logger.info("Indexing agenda/minutes docs under {}", SCRAPE_ROOT)
    candidates = index_all(jurisdiction=args.jurisdiction)
    _report(candidates)

    if args.extract:
        return _extract_and_merge_guard(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
