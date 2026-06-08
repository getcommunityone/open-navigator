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

All four stages are implemented. INDEX + MATCH (1-2) are free and run by default.
EXTRACT + MERGE (3-4) are billed and strictly opt-in: ``--extract`` does nothing
unless BOTH ``--jurisdiction <id>`` and ``--limit N`` are given, so a billed
Gemini run can never happen by accident (keys are BILLED — a prior full-US run
cost ~$22). Each extraction logs a "🔸 BILLED Gemini call" line per document.

Documents live on disk under
``data/cache/scraped_meetings/<ST>/<segment>/<jid>/`` — indexed per jurisdiction
in ``_manifest.json`` (key ``pdfs[]``, a MIXED-document list: pdf/docx/doc/ashx),
plus HTML agendas saved as CivicPlus pages under ``_crawl_html/page__*.html``.

Usage::

    # FREE: discover + report coverage (default)
    python -m llm.gemini.meeting_document_enrichment
    python -m llm.gemini.meeting_document_enrichment --jurisdiction hampshire_25015

    # BILLED (opt-in, scoped): extract matched docs and merge into the analysis.
    python -m llm.gemini.meeting_document_enrichment --extract --jurisdiction <id> --limit 5
    # Widen the doc<->meeting date match when a jurisdiction lists docs off the
    # exact meeting date (e.g. minutes posted days later):
    python -m llm.gemini.meeting_document_enrichment --extract --jurisdiction <id> --limit 5 --window-days 7
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Iterable, Optional

from loguru import logger

from llm.gemini.genai_text_client import (
    call_gemini_text,
    default_flash_lite_model,
    ensure_valid_gemini_api_key,
    extract_json_from_model_text,
)

# Repo root (…/open-navigator) — five parents up from this module file.
PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCRAPE_ROOT = PROJECT_ROOT / "data" / "cache" / "scraped_meetings"
# Transcript-policy analysis output (the MERGE target). Same <ST>/<segment>/<jid>
# scheme as the scrape cache, so docs and meetings join on that path triple.
ANALYSIS_ROOT = PROJECT_ROOT / "data" / "cache" / "gemini_transcript_policy"
# Analysis filename leads with the meeting date; "unknown-date_*" = non-meeting
# YouTube content (educational shorts etc.), skipped from matching.
_ANALYSIS_DATE_RE = re.compile(r"^(20\d{2}-\d{2}-\d{2})_")

# doc_type values (in manifest pdfs[]) we treat as agenda/minutes content.
AGENDA_MINUTES_DOC_TYPES = {"agenda", "minutes", "agenda_packet", "packet"}
# Extensions we can normalize for extraction (audio/video are skipped).
SUPPORTED_EXTS = {"pdf", "docx", "doc", "html", "htm", "ashx"}
# HTML page filenames (CivicPlus AgendaCenter / DocumentCenter) that are agendas
# or minutes. These are NOT in pdfs[]; they're scraped pages under _crawl_html/.
_HTML_DOC_RE = re.compile(r"(agenda|minute|documentcenter)", re.IGNORECASE)

# Date patterns seen in anchor_text / filenames: 20260312, 3.12.26, 04072026,
# 2026-03-12, 03/12/2026, March 12 2026. Best-effort — MATCH stays conservative.
# The contiguous YYYYMMDD form is FIRST on purpose: doc filenames carry the real
# meeting date as `20260506-Agenda.pdf`, while the wp-content upload path
# (`/wp-content/uploads/2026/05/`) is only the *upload* month. Without this, the
# greedy `2026/05/<dd>` rule below latched onto the upload dir + the filename's
# leading "20" and collapsed every doc to one bogus date (e.g. 2026-05-20).
_DATE_PATTERNS = [
    re.compile(r"\b(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})\b"),                   # 20260312 (YYYYMMDD)
    re.compile(r"(?P<y>20\d{2})[-_/.](?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})"),       # 2026-03-12
    re.compile(r"(?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})[-_/.](?P<y>20\d{2})"),       # 03/12/2026
    re.compile(r"(?P<m>\d{1,2})[-_/.](?P<d>\d{1,2})[-_/.](?P<yy>\d{2})\b"),      # 3.12.26
    re.compile(r"\b(?P<m>\d{2})(?P<d>\d{2})(?P<y>20\d{2})\b"),                   # 04072026 (MMDDYYYY)
]


@dataclass
class DocCandidate:
    """One agenda/minutes document found on disk, before any extraction."""

    jurisdiction_id: str
    juris_path: str                     # <ST>/<segment>/<jid> — join key to meetings
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


# Canonical body-category tokens — mirrors dbt macro normalize_meeting_body_key.sql
# so this script keys bodies the SAME way the event_meeting_document mart does.
# Adds 'county_commission' (the macro is city-centric; scraped county docs — e.g.
# tuscco.com — identify as a County Commission, a different body than the City
# Council videos bucketed under the same county FIPS). Order = specific first.
_BODY_TIME_RE = re.compile(r"^\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*", re.I)
_BODY_FILLER_RE = re.compile(r"(\s*-\s*canceled\s*$|\s+meeting\s*$)", re.I)
_BODY_RULES: list[tuple[str, str]] = [
    ("work session", "work_session"),
    ("canvass", "election"), ("election", "election"),
    ("community development", "community_development"),
    ("public safety", "public_safety"), ("safety", "public_safety"),
    ("public projects", "projects"), ("projects", "projects"),
    ("litigation", "litigation_insurance"), ("insurance", "litigation_insurance"),
    ("administration", "administration"),
    ("finance", "finance"),
    ("properties", "properties"),
    ("historic", "historic"),
    ("riverfront", "riverfront"),
    ("zoning board", "zoning_board"),
    ("planning", "planning"), ("zoning", "planning"),
    ("county commission", "county_commission"),
    ("city council", "council"), ("council", "council"),
]


def _normalize_body_key(text: Optional[str]) -> Optional[str]:
    """Free-text body label -> canonical token (mirrors the dbt macro). None if unrecognized.

    Returning None on an unknown body is deliberate: the guard only rejects a
    merge when BOTH sides resolve to a token AND they differ — never on a guess.
    """
    if not text:
        return None
    t = _BODY_TIME_RE.sub("", text.replace("_", " ").lower())
    t = _BODY_FILLER_RE.sub("", t)
    for needle, token in _BODY_RULES:
        if needle in t:
            return token
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
    juris_path = "/".join(p for p in (state, segment, jid) if p)

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
            juris_path=juris_path,
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
                juris_path=juris_path,
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
# Stage 2 — MATCH: link candidate docs to analyzed meetings (FREE, no Gemini).
# ---------------------------------------------------------------------------
@dataclass
class AnalyzedMeeting:
    juris_path: str        # <ST>/<segment>/<jid> — same key as DocCandidate.juris_path
    iso_date: str          # meeting date (from the analysis filename prefix)
    name: str
    analysis_path: str     # the policy-analysis JSON (the MERGE target)


def iter_analyzed_meetings(jurisdiction: Optional[str] = None) -> list[AnalyzedMeeting]:
    """Analyzed meetings from the transcript-policy cache (02_analysis JSONs).

    Skips ``unknown-date_*`` files (non-meeting YouTube content). Date comes from
    the filename prefix — cheap and avoids opening every JSON.
    """
    out: list[AnalyzedMeeting] = []
    for jp in ANALYSIS_ROOT.glob("*/*/*/*/02_analysis/*.json"):
        rel = jp.relative_to(ANALYSIS_ROOT).parts  # ST, segment, jid, channel, 02_analysis, file
        if len(rel) < 6:
            continue
        m = _ANALYSIS_DATE_RE.match(rel[-1])
        if not m:
            continue
        juris_path = f"{rel[0]}/{rel[1]}/{rel[2]}"
        if jurisdiction and jurisdiction not in juris_path:
            continue
        out.append(AnalyzedMeeting(
            juris_path=juris_path,
            iso_date=m.group(1),
            name=rel[-1][:-5],
            analysis_path=str(jp),
        ))
    return out


def _to_date(iso: Optional[str]) -> Optional[date_cls]:
    try:
        return date_cls.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def match_docs_to_meetings(
    candidates: list[DocCandidate],
    meetings: list[AnalyzedMeeting],
    window_days: int = 0,
) -> dict:
    """For each analyzed meeting, find same-jurisdiction docs within ``window_days``.

    Returns coverage counts + a few example matches. window_days=0 means the
    agenda/minutes date must equal the meeting date (the strong signal).
    """
    by_juris: dict[str, list[DocCandidate]] = collections.defaultdict(list)
    for c in candidates:
        if c.iso_date and c.juris_path:
            by_juris[c.juris_path].append(c)

    total = matched_any = matched_agenda = matched_minutes = 0
    examples: list[tuple[AnalyzedMeeting, list[DocCandidate]]] = []
    for mtg in meetings:
        md = _to_date(mtg.iso_date)
        if not md:
            continue
        total += 1
        hits = [
            c for c in by_juris.get(mtg.juris_path, [])
            if (cd := _to_date(c.iso_date)) and abs((cd - md).days) <= window_days
        ]
        if not hits:
            continue
        matched_any += 1
        if any(c.doc_type in ("agenda", "agenda_packet", "packet") for c in hits):
            matched_agenda += 1
        if any(c.doc_type == "minutes" for c in hits):
            matched_minutes += 1
        if len(examples) < 6:
            examples.append((mtg, hits))
    return {
        "meetings": total,
        "matched_any": matched_any,
        "matched_agenda": matched_agenda,
        "matched_minutes": matched_minutes,
        "examples": examples,
    }


def _report_match(candidates: list[DocCandidate], jurisdiction: Optional[str]) -> None:
    meetings = iter_analyzed_meetings(jurisdiction=jurisdiction)
    logger.info("Analyzed meetings (dated) to enrich: {}", len(meetings))
    for window in (0, 7):
        r = match_docs_to_meetings(candidates, meetings, window_days=window)
        pct = (100 * r["matched_any"] / r["meetings"]) if r["meetings"] else 0
        logger.success(
            "±{}d: {}/{} meetings ({:.0f}%) matched a doc — agenda {}, minutes {}",
            window, r["matched_any"], r["meetings"], pct, r["matched_agenda"], r["matched_minutes"],
        )
    # examples from the exact-date tier
    for mtg, hits in match_docs_to_meetings(candidates, meetings, 0)["examples"]:
        kinds = ", ".join(sorted({f"{h.doc_type}/{h.fmt}" for h in hits}))
        logger.info("  {} {} -> {}", mtg.iso_date, mtg.juris_path, kinds)


# ---------------------------------------------------------------------------
# Stage 3 — NORMALIZE (any format -> text) + EXTRACT (Gemini, BILLED).
# ---------------------------------------------------------------------------
# Cap the text we send so a giant packet can't blow the token budget.
_MAX_DOC_CHARS = 200_000
# Below this much extracted text a PDF is treated as scanned (no text layer) and
# sent to Gemini as native PDF bytes (vision). Vision is pricier, so we only use
# it when cheap text extraction comes up (near-)empty.
_MIN_TEXT_CHARS = 400
# Inline PDF parts are capped (~20 MB); above this we don't attempt vision.
_MAX_PDF_BYTES = 18_000_000

_EXTRACT_SYSTEM = """You extract the OFFICIAL structure of a municipal meeting AGENDA or MINUTES document for a civic-data platform. Return ONLY a JSON object — no prose, no markdown fences.

Extract exactly what the document states. NEVER infer or fabricate; use null or [] when something is absent. If it is an agenda (no outcomes yet), leave disposition/motions/recorded_votes/continuances empty.

{
  "doc_kind": "agenda" | "minutes",
  "meeting_body": "string or null",
  "meeting_date": "YYYY-MM-DD or null",
  "agenda_items": [
    {"item_number": "string or null (e.g. '7.A', 'Ordinance 2024-15')",
     "title": "string",
     "disposition": "string or null (minutes only: approved/denied/tabled/continued/withdrawn)"}
  ],
  "motions": [{"on_item": "string or null", "moved_by": "string or null", "seconded_by": "string or null", "text": "string or null"}],
  "recorded_votes": [{"on_item": "string or null", "yes": "int or null", "no": "int or null", "abstain": "int or null", "result": "string or null"}],
  "continuances": [{"item": "string", "continued_to": "string or null (date or future meeting)"}],
  "legislation_numbers": ["string"]
}"""


def _normalize_to_text(candidate: "DocCandidate") -> Optional[str]:
    """Extract plain text from a doc of any supported format. None if it can't."""
    path = candidate.local_path
    if not path or not Path(path).exists():
        logger.warning("Missing local file: {}", path)
        return None
    fmt = candidate.fmt
    try:
        if fmt in ("pdf", "ashx"):  # ashx is usually a PDF behind a handler
            import fitz  # PyMuPDF
            with fitz.open(path) as doc:
                return "\n".join(page.get_text() for page in doc).strip() or None
        if fmt == "docx":
            from docx import Document
            return "\n".join(p.text for p in Document(path).paragraphs).strip() or None
        if fmt in ("html", "htm"):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(Path(path).read_text(encoding="utf-8", errors="ignore"), "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(" ", strip=True) or None
        if fmt == "doc":  # legacy binary .doc — no pure-python reader; skip
            logger.warning("Legacy .doc not supported (skip): {}", path)
            return None
    except Exception as exc:  # noqa: BLE001 — one bad doc must not kill the run
        logger.warning("Text extraction failed for {} ({}): {}", path, fmt, exc)
        return None
    return None


def _extract_doc(candidate: "DocCandidate", api_key: str, model: str) -> Optional[dict]:
    """Normalize -> Gemini -> parsed JSON. None on any failure (logged).

    Cost order: try CHEAP text extraction first; only fall back to (pricier)
    Gemini PDF-vision when a PDF has no usable text layer (i.e. it's scanned).
    """
    path = candidate.local_path
    if not path or not Path(path).exists():
        logger.warning("Missing local file: {}", path)
        return None

    pdf_bytes: Optional[bytes] = None
    text = _normalize_to_text(candidate) or ""

    if candidate.fmt in ("pdf", "ashx") and len(text) < _MIN_TEXT_CHARS:
        # Scanned / no text layer — read the bytes and let Gemini read it visually.
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            logger.warning("Cannot read {}: {}", path, exc)
            return None
        if len(data) <= _MAX_PDF_BYTES:
            logger.info("No text layer ({} chars) — falling back to Gemini PDF vision: {}", len(text), path)
            pdf_bytes, text = data, ""
        elif not text:
            logger.warning("Scanned PDF too large for inline vision ({} bytes), skipping: {}", len(data), path)
            return None

    if not pdf_bytes and not text:
        return None
    if text and len(text) > _MAX_DOC_CHARS:
        text = text[:_MAX_DOC_CHARS]

    logger.warning(
        "🔸 BILLED Gemini call: {} ({}, {}) [{}]",
        candidate.doc_type, candidate.fmt, candidate.iso_date, "vision" if pdf_bytes else "text",
    )
    try:
        result = call_gemini_text(
            api_key=api_key, model=model,
            system_instruction=_EXTRACT_SYSTEM,
            user_text="doc_type hint: " + candidate.doc_type + ("" if pdf_bytes else "\n\n" + text),
            pdf_bytes=pdf_bytes,
        )
        data = extract_json_from_model_text(result.text)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.error("Gemini extraction failed for {}: {}", path, exc)
        return None


# ---------------------------------------------------------------------------
# Stage 4 — MERGE the extracted structure into the meeting's analysis JSON.
# ---------------------------------------------------------------------------
def _merge_into_analysis(meeting: "AnalyzedMeeting", hits: list["DocCandidate"], extracted: dict) -> bool:
    """Add a `meeting_documents` block to the analysis JSON (non-destructive)."""
    try:
        analysis = json.loads(Path(meeting.analysis_path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.error("Cannot read analysis JSON {}: {}", meeting.analysis_path, exc)
        return False

    block = analysis.get("meeting_documents")
    if not isinstance(block, dict):
        block = {"sources": []}
    block["enriched_by"] = "meeting_document_enrichment"
    block.setdefault("sources", [])
    for h in hits:
        src = {"doc_type": h.doc_type, "fmt": h.fmt, "url": h.url, "local_path": h.local_path, "iso_date": h.iso_date}
        if src not in block["sources"]:
            block["sources"].append(src)
    # File the extracted structure under agenda/ minutes by the model's doc_kind.
    kind = (extracted.get("doc_kind") or "").lower()
    slot = "minutes" if "minute" in kind else "agenda"
    block[slot] = extracted
    analysis["meeting_documents"] = block
    # NON-DESTRUCTIVE: we add a block; transcript-derived decisions[] are untouched.
    Path(meeting.analysis_path).write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return True


# ---------------------------------------------------------------------------
# Stage 5 — LOAD the merged meeting_documents blocks into a public serving table
# (public.meeting_document), so the API can attach agenda/minutes to a decision.
# Keyed by (jurisdiction_jid, meeting_date, doc_kind) — the API joins it to a
# decision via event_meeting (jurisdiction + date). Direct-to-public load follows
# the hosting.neon.migrate precedent for derived serving tables (no clean FK to
# event_meeting since the join is a composite jurisdiction+date heuristic).
# ---------------------------------------------------------------------------
_MEETING_DOC_DDL = """
CREATE TABLE IF NOT EXISTS public.meeting_document (
    jurisdiction_jid    TEXT NOT NULL,
    meeting_date        DATE NOT NULL,
    doc_kind            TEXT NOT NULL,           -- 'agenda' | 'minutes'
    meeting_body        TEXT,
    agenda_items        JSONB,
    motions             JSONB,
    recorded_votes      JSONB,
    continuances        JSONB,
    legislation_numbers JSONB,
    source_urls         JSONB,
    updated_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (jurisdiction_jid, meeting_date, doc_kind)
);
CREATE INDEX IF NOT EXISTS meeting_document_juris_date_idx
    ON public.meeting_document (jurisdiction_jid, meeting_date);
"""

_MEETING_ID_RE = re.compile(r"^(?P<jid>.+)_(?P<date>\d{4}-\d{2}-\d{2})$")


def _local_dsn() -> str:
    import os
    return os.getenv("LOCAL_DATABASE_URL", "postgresql://postgres:password@localhost:5433/open_navigator")


def load_to_warehouse(jurisdiction: Optional[str] = None) -> int:
    """Upsert merged meeting_documents blocks → public.meeting_document. Returns rows."""
    import json as _json

    import psycopg2
    from psycopg2.extras import Json, execute_values

    # Keyed by (jid, date, doc_kind) so duplicate analysis files for the same
    # meeting collapse to one row (ON CONFLICT can't update a PK twice per batch).
    rows: dict[tuple, tuple] = {}
    for jp in ANALYSIS_ROOT.glob("*/*/*/*/02_analysis/*.json"):
        if jurisdiction and jurisdiction not in str(jp):
            continue
        try:
            data = _json.loads(jp.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        md = data.get("meeting_documents")
        if not isinstance(md, dict):
            continue
        meeting_id = ((data.get("meeting") or {}).get("meeting_id")) or ""
        m = _MEETING_ID_RE.match(meeting_id)
        if not m:
            continue
        jid, mdate = m.group("jid"), m.group("date")
        src_urls = [s.get("url") for s in (md.get("sources") or []) if s.get("url")]
        for slot in ("agenda", "minutes"):
            blk = md.get(slot)
            if not isinstance(blk, dict):
                continue
            rows[(jid, mdate, slot)] = (
                jid, mdate, slot, blk.get("meeting_body"),
                Json(blk.get("agenda_items") or []), Json(blk.get("motions") or []),
                Json(blk.get("recorded_votes") or []), Json(blk.get("continuances") or []),
                Json(blk.get("legislation_numbers") or []), Json(src_urls),
            )
    if not rows:
        logger.warning("No merged meeting_documents found to load (jurisdiction={})", jurisdiction)
        return 0

    conn = psycopg2.connect(_local_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute(_MEETING_DOC_DDL)
            execute_values(cur, """
                INSERT INTO public.meeting_document
                  (jurisdiction_jid, meeting_date, doc_kind, meeting_body, agenda_items,
                   motions, recorded_votes, continuances, legislation_numbers, source_urls)
                VALUES %s
                ON CONFLICT (jurisdiction_jid, meeting_date, doc_kind) DO UPDATE SET
                  meeting_body=EXCLUDED.meeting_body, agenda_items=EXCLUDED.agenda_items,
                  motions=EXCLUDED.motions, recorded_votes=EXCLUDED.recorded_votes,
                  continuances=EXCLUDED.continuances, legislation_numbers=EXCLUDED.legislation_numbers,
                  source_urls=EXCLUDED.source_urls, updated_at=now()
            """, list(rows.values()))
        conn.commit()
    finally:
        conn.close()
    logger.success("Loaded {} meeting_document rows into public.meeting_document", len(rows))
    return len(rows)


def run_extract(args: argparse.Namespace) -> int:
    """Scoped, opt-in BILLED enrichment: extract matched docs and merge (per jurisdiction)."""
    if not (args.jurisdiction and args.limit and args.limit > 0):
        logger.error(
            "--extract requires --jurisdiction <id> AND --limit N (billed Gemini; "
            "scoped runs only — never all jurisdictions at once)."
        )
        return 2

    api_key = ensure_valid_gemini_api_key(model=args.model or default_flash_lite_model())
    model = (args.model or default_flash_lite_model()).strip()
    candidates = index_all(jurisdiction=args.jurisdiction)
    meetings = iter_analyzed_meetings(jurisdiction=args.jurisdiction)
    by_juris: dict[str, list[DocCandidate]] = collections.defaultdict(list)
    for c in candidates:
        if c.iso_date and c.juris_path:
            by_juris[c.juris_path].append(c)

    # Meetings (with a matched doc) to enrich, capped by --limit. window_days=0
    # (default) requires the doc date to equal the meeting date (strong signal);
    # widen it for jurisdictions that post minutes a few days off the meeting.
    window_days = max(0, args.window_days or 0)
    targets: list[tuple[AnalyzedMeeting, list[DocCandidate]]] = []
    for mtg in meetings:
        md = _to_date(mtg.iso_date)
        if not md:
            continue
        hits = [
            c for c in by_juris.get(mtg.juris_path, [])
            if (cd := _to_date(c.iso_date)) and abs((cd - md).days) <= window_days
        ]
        if hits:
            targets.append((mtg, hits))
    targets = targets[: args.limit]
    if not targets:
        logger.warning(
            "No doc matches (±{}d) for jurisdiction '{}' — nothing to extract. "
            "Try a wider --window-days if minutes post off the meeting date.",
            window_days, args.jurisdiction,
        )
        return 0

    # Extract each UNIQUE doc ONCE. A doc can match several meetings (a packet
    # spanning bodies on one day, or a wider --window-days), and re-extracting it
    # per meeting is wasted billing — a prior run billed 17 docs 5× each.
    def _doc_key(c: DocCandidate) -> str:
        return c.local_path or c.url or f"{c.juris_path}|{c.doc_type}|{c.iso_date}"

    unique_docs: dict[str, DocCandidate] = {}
    for _mtg, hits in targets:
        for h in hits:
            unique_docs.setdefault(_doc_key(h), h)

    logger.warning(
        "⚠️ BILLED run: {} meeting(s), {} unique doc(s), model={}, ±{}d match",
        len(targets), len(unique_docs), model, window_days,
    )
    extracted_by_key: dict[str, dict] = {}
    for key, h in unique_docs.items():
        data = _extract_doc(h, api_key, model)
        if data is not None:
            extracted_by_key[key] = data

    enriched = 0
    for mtg, hits in targets:
        merged_any = False
        for h in hits:
            data = extracted_by_key.get(_doc_key(h))
            if data and _merge_into_analysis(mtg, [h], data):
                merged_any = True
        if merged_any:
            enriched += 1
            logger.success("✅ Enriched {} {}", mtg.juris_path, mtg.iso_date)
    logger.success(
        "Done — enriched {}/{} meetings from {} unique doc(s) extracted",
        enriched, len(targets), len(extracted_by_key),
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jurisdiction", help="Limit to a jurisdiction substring (e.g. baldwin_01003)")
    parser.add_argument("--match", action="store_true", help="Also link docs to analyzed meetings and report coverage (free)")
    parser.add_argument("--load", action="store_true", help="Load merged meeting_documents into public.meeting_document (free)")
    parser.add_argument("--extract", action="store_true", help="(BILLED, opt-in) run Gemini extraction — requires --jurisdiction + --limit")
    parser.add_argument("--limit", type=int, default=0, help="Max meetings to extract in one run (extraction only)")
    parser.add_argument("--window-days", type=int, default=0, help="Doc<->meeting date match window in days for extraction (default 0 = exact date)")
    parser.add_argument("--model", help="Gemini model (default: flash-lite)")
    args = parser.parse_args(argv)

    if not SCRAPE_ROOT.is_dir():
        logger.error("Scrape cache not found: {}", SCRAPE_ROOT)
        return 1

    logger.info("Indexing agenda/minutes docs under {}", SCRAPE_ROOT)
    candidates = index_all(jurisdiction=args.jurisdiction)
    _report(candidates)

    if args.match or args.extract:
        _report_match(candidates, args.jurisdiction)

    if args.extract:
        return run_extract(args)
    if args.load:
        load_to_warehouse(jurisdiction=args.jurisdiction)
    return 0


if __name__ == "__main__":
    sys.exit(main())
