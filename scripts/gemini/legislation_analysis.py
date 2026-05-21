"""
Validate legislation cross-refs in Part 1 analysis JSON and map agenda labels → leg_id.

Used after Gemini Part 1 (fix orphan ``legislation_refs``) and when building transcript
hints (agenda item numbers / case IDs from captions).
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

# Agenda / case identifiers spoken in council video captions
_AGENDA_ITEM_RE = re.compile(
    r"(?:agenda\s+)?item\s+(?:number\s+)?(\d+[A-Za-z]?(?:\s*[A-Za-z]\d+)?)",
    re.I,
)
_ORDINANCE_RE = re.compile(
    r"(?:ordinance|resolution|zoning\s+amendment|amendment)\s+(?:number\s+)?(\d+[\w-]*)",
    re.I,
)
_CASE_ID_RE = re.compile(
    r"\b([ZS]\d{4,5})\b",
    re.I,
)
_ITEM_ID_RE = re.compile(r"^(U|D)\d{3}$", re.I)


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def legislation_index(analysis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """leg_id → legislation row."""
    out: Dict[str, Dict[str, Any]] = {}
    for row in analysis.get("legislation") or []:
        if isinstance(row, dict) and row.get("leg_id"):
            out[str(row["leg_id"])] = row
    return out


def fuzzy_match_leg_id(
    ref: str,
    legislation: List[Dict[str, Any]],
) -> Optional[str]:
    """Match orphan ref to a legislation[] row by leg_id substring or official_number."""
    ref = (ref or "").strip()
    if not ref:
        return None
    ref_n = _norm_key(ref)
    for leg in legislation:
        lid = str(leg.get("leg_id") or "")
        if not lid:
            continue
        if ref == lid or ref_n == _norm_key(lid):
            return lid
        off = str(leg.get("official_number") or "")
        if off and (_norm_key(off) in ref_n or ref_n in _norm_key(lid)):
            return lid
        title = str(leg.get("title") or "")
        if off and off.lower() in title.lower():
            return lid
    return None


def validate_and_fix_legislation_refs(
    analysis: Dict[str, Any],
    *,
    fix: bool = True,
    drop_orphans: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Ensure ``legislation_refs`` and ``subjects[].canonical_leg_id`` point at ``legislation[]``.

    Returns (patched analysis, validation report). Report is also stored on
    ``analysis['_legislation_validation']`` when fix=True.
    """
    out = copy.deepcopy(analysis)
    legislation = [
        x for x in (out.get("legislation") or []) if isinstance(x, dict)
    ]
    leg_ids = {str(x["leg_id"]) for x in legislation if x.get("leg_id")}

    report: Dict[str, Any] = {
        "legislation_count": len(leg_ids),
        "orphan_refs": [],
        "fixed_refs": [],
        "invalid_canonical_leg_id": [],
        "items_checked": 0,
    }

    def _fix_ref_list(refs: Any, *, ctx: str) -> List[str]:
        if not isinstance(refs, list):
            return []
        good: List[str] = []
        for raw in refs:
            ref = str(raw or "").strip()
            if not ref:
                continue
            report["items_checked"] += 1
            if ref in leg_ids:
                good.append(ref)
                continue
            matched = fuzzy_match_leg_id(ref, legislation) if fix else None
            if matched:
                good.append(matched)
                report["fixed_refs"].append({"context": ctx, "from": ref, "to": matched})
                leg_ids.add(matched)
            elif drop_orphans:
                report["orphan_refs"].append({"context": ctx, "ref": ref})
            else:
                good.append(ref)
        # stable dedupe
        seen: set[str] = set()
        deduped: List[str] = []
        for r in good:
            if r not in seen:
                seen.add(r)
                deduped.append(r)
        return deduped

    for bucket in ("decisions", "uncontested_items"):
        for row in out.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            iid = str(row.get("item_id") or row.get("decision_id") or "")
            ctx = f"{bucket}:{iid or row.get('headline', '')[:40]}"
            row["legislation_refs"] = _fix_ref_list(row.get("legislation_refs"), ctx=ctx)

    for subj in out.get("subjects") or []:
        if not isinstance(subj, dict):
            continue
        cid = str(subj.get("canonical_leg_id") or "").strip()
        if not cid:
            continue
        if cid in leg_ids:
            continue
        matched = fuzzy_match_leg_id(cid, legislation) if fix else None
        if matched:
            report["fixed_refs"].append(
                {"context": f"subject:{subj.get('subject_id')}", "from": cid, "to": matched}
            )
            subj["canonical_leg_id"] = matched
            leg_ids.add(matched)
        else:
            report["invalid_canonical_leg_id"].append(
                {"subject_id": subj.get("subject_id"), "canonical_leg_id": cid}
            )
            if fix and drop_orphans:
                subj["canonical_leg_id"] = None

    report["ok"] = not report["orphan_refs"] and not report["invalid_canonical_leg_id"]
    if fix:
        out["_legislation_validation"] = report
    return out, report


def extract_agenda_labels_from_text(text: str) -> List[str]:
    """Pull agenda labels (e.g. ``10``, ``10 C1``, ``Z0726``) from a caption line."""
    labels: List[str] = []
    t = text or ""
    for m in _AGENDA_ITEM_RE.finditer(t):
        labels.append(m.group(1).replace(" ", "").strip())
    for m in _ORDINANCE_RE.finditer(t):
        labels.append(m.group(1).strip())
    for m in _CASE_ID_RE.finditer(t):
        labels.append(m.group(1).upper())
    return labels


def build_agenda_label_to_leg_id(analysis: Dict[str, Any]) -> Dict[str, str]:
    """
    Map agenda/case labels → ``leg_id`` using ``legislation[].official_number`` and slug text.
    """
    mapping: Dict[str, str] = {}
    for leg in analysis.get("legislation") or []:
        if not isinstance(leg, dict):
            continue
        lid = str(leg.get("leg_id") or "").strip()
        if not lid:
            continue
        off = str(leg.get("official_number") or "").strip()
        if off:
            mapping[_norm_key(off)] = lid
            mapping[off.upper()] = lid
            mapping[off.lower()] = lid
        # slug contains official number (e.g. z0726_2026_...)
        for m in _CASE_ID_RE.finditer(lid):
            mapping[m.group(1).upper()] = lid
        for m in _CASE_ID_RE.finditer(str(leg.get("title") or "")):
            mapping[m.group(1).upper()] = lid
    return mapping


def format_pre_gemini_agenda_legislation_hints(
    agenda_blocks: List[Dict[str, Any]],
    *,
    jurisdiction_id: str,
) -> str:
    """
    Pre-Gemini hint block: agenda item numbers / case IDs seen in captions (no leg_id yet).
    """
    if not agenda_blocks:
        return ""
    lines = [
        "=== AGENDA LEGISLATION HINTS (caption cues → legislation[].leg_id) ===",
        f"jurisdiction_id: {jurisdiction_id}",
        "When you add legislation[], include official_number (e.g. Z0726, 10 C1, Resolution 2025-4).",
        "Set legislation_refs on each U*/D* row to the matching leg_id slug.",
        "",
    ]
    for i, block in enumerate(agenda_blocks, 1):
        topic = (block.get("topic_snippet") or "").replace("\n", " ")
        labels = extract_agenda_labels_from_text(topic)
        label_s = ", ".join(labels) if labels else "(listen for ordinance/resolution number)"
        lines.append(f"block_{i:02d} | agenda_labels={label_s} | topic={topic[:100]}")
    lines.append("")
    return "\n".join(lines)


def ingest_agenda_legislation(
    analysis: Dict[str, Any],
    *,
    agenda_blocks: Optional[List[Dict[str, Any]]] = None,
    fix_refs: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    After Part 1: attach ``agenda_labels`` on items and fill missing ``legislation_refs``.

    Also builds top-level ``agenda_legislation_map[]`` for bronze persistence.
    """
    out = copy.deepcopy(analysis)
    label_to_leg = build_agenda_label_to_leg_id(out)
    ingest_report: Dict[str, Any] = {
        "labels_mapped": 0,
        "refs_added": 0,
        "agenda_rows": [],
    }

    block_labels: List[str] = []
    if agenda_blocks:
        for block in agenda_blocks:
            topic = block.get("topic_snippet") or ""
            block_labels.extend(extract_agenda_labels_from_text(topic))

    agenda_map: List[Dict[str, Any]] = []

    def _labels_for_row(row: Dict[str, Any]) -> List[str]:
        text = " ".join(
            str(row.get(k) or "")
            for k in ("headline", "one_line_summary", "decision_statement", "motion")
        )
        labels = extract_agenda_labels_from_text(text)
        # positional: first uncontested ↔ first block (weak fallback)
        return labels

    for bucket, kind in (("uncontested_items", "uncontested"), ("decisions", "decision")):
        for row in out.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            labels = _labels_for_row(row)
            item_key = str(row.get("item_id") or row.get("decision_id") or "")
            leg_ids_for_item: List[str] = []
            for lab in labels:
                lid = label_to_leg.get(_norm_key(lab)) or label_to_leg.get(lab.upper())
                if not lid:
                    continue
                leg_ids_for_item.append(lid)
                ingest_report["labels_mapped"] += 1
            if labels:
                row["agenda_labels"] = labels
            refs = list(row.get("legislation_refs") or [])
            before = len(refs)
            for lid in leg_ids_for_item:
                if lid not in refs:
                    refs.append(lid)
            if len(refs) > before:
                ingest_report["refs_added"] += len(refs) - before
            row["legislation_refs"] = refs
            if labels or refs:
                agenda_map.append(
                    {
                        "item_id": item_key,
                        "item_kind": kind,
                        "agenda_labels": labels,
                        "leg_ids": refs,
                        "headline": (row.get("headline") or "")[:200],
                    }
                )

    out["agenda_legislation_map"] = agenda_map
    ingest_report["agenda_rows"] = len(agenda_map)
    out["_agenda_legislation_ingest"] = ingest_report

    if fix_refs:
        out, val_report = validate_and_fix_legislation_refs(out, fix=True)
        out["_legislation_validation"] = val_report
    return out, ingest_report


def enrich_part1_legislation(
    analysis: Dict[str, Any],
    *,
    agenda_blocks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Validate/fix refs, then agenda ingest (single post-Part-1 entry point)."""
    out, _ = ingest_agenda_legislation(
        analysis, agenda_blocks=agenda_blocks, fix_refs=True
    )
    return out
