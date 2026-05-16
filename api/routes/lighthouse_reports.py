"""
Lighthouse audit report payload for the Data explorer UI.

Reads ``bronze.bronze_jurisdiction_website_lighthouse`` (same table as accessibility persist).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from api.routes.stats_neon import get_db_pool

router = APIRouter(prefix="/lighthouse", tags=["lighthouse"])

BRONZE_LIGHTHOUSE = "bronze.bronze_jurisdiction_website_lighthouse"


class LighthouseScores(BaseModel):
    performance: Optional[int] = None
    accessibility: Optional[int] = None
    best_practices: Optional[int] = None
    seo: Optional[int] = None


class LighthouseReportResponse(BaseModel):
    scan_key: str
    batch_id: str
    jurisdiction_id: str
    website_url: str
    final_url: Optional[str] = None
    scanned_at: Optional[str] = None
    status: str
    lighthouse_version: Optional[str] = None
    requested_url: Optional[str] = Field(None, description="From LHR requestedUrl when present")
    scores: LighthouseScores
    run_warnings: List[str] = Field(default_factory=list)
    screenshot_data_url: Optional[str] = Field(
        None, description="data: URL when final-screenshot is present in LHR"
    )


def _url_variants(url: str) -> List[str]:
    u = (url or "").strip()
    if not u:
        return []
    no_slash = u.rstrip("/")
    with_slash = no_slash + "/"
    return list(dict.fromkeys([u, no_slash, with_slash]))


def _dict_from_results(results: Any) -> Dict[str, Any]:
    if isinstance(results, dict):
        return results
    if results is None:
        return {}
    try:
        import json

        if isinstance(results, (bytes, bytearray)):
            results = results.decode("utf-8")
        if isinstance(results, str):
            return dict(json.loads(results))
    except Exception:
        return {}
    return {}


def _lhr_from_row(row_results: Any) -> Optional[Dict[str, Any]]:
    blob = _dict_from_row(row_results)
    lhr = blob.get("lhr")
    if isinstance(lhr, dict):
        return lhr
    return None


def _score_to_int100(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        v = float(val)
        if v <= 1.0:
            return int(round(v * 100))
        return int(round(v))
    except (TypeError, ValueError):
        return None


def _category_score(lhr: Optional[Dict[str, Any]], key: str) -> Optional[int]:
    if not lhr:
        return None
    cats = lhr.get("categories")
    if not isinstance(cats, dict):
        return None
    cat = cats.get(key)
    if not isinstance(cat, dict):
        return None
    return _score_to_int100(cat.get("score"))


def _merge_score(column: Optional[int], lhr: Optional[Dict[str, Any]], cat_key: str) -> Optional[int]:
    if column is not None:
        return column
    return _category_score(lhr, cat_key)


def _extract_screenshot_data_url(lhr: Optional[Dict[str, Any]]) -> Optional[str]:
    if not lhr:
        return None
    audits = lhr.get("audits")
    if not isinstance(audits, dict):
        return None
    for key in ("final-screenshot", "full-page-screenshot"):
        audit = audits.get(key)
        if not isinstance(audit, dict):
            continue
        details = audit.get("details")
        if not isinstance(details, dict):
            continue
        if details.get("type") == "screenshot" and details.get("data"):
            data = str(details["data"])
            mime = "image/jpeg"
            return f"data:{mime};base64,{data}"
        items = details.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict) and first.get("data"):
                data = str(first["data"])
                return f"data:image/jpeg;base64,{data}"
    thumbs = audits.get("screenshot-thumbnails")
    if isinstance(thumbs, dict):
        det = thumbs.get("details")
        if isinstance(det, dict):
            items = det.get("items")
            if isinstance(items, list) and items:
                last = items[-1]
                if isinstance(last, dict) and last.get("data"):
                    return f"data:image/jpeg;base64,{str(last['data'])}"
    return None


def _warnings_from_lhr(lhr: Optional[Dict[str, Any]]) -> List[str]:
    if not lhr:
        return []
    raw = lhr.get("runWarnings")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for w in raw:
        if isinstance(w, str) and w.strip():
            out.append(w.strip())
    return out


@router.get("/report", response_model=LighthouseReportResponse)
async def get_lighthouse_report(
    website_url: str = Query(..., min_length=4, description="Homepage URL as stored in website_url"),
    batch_id: Optional[str] = Query(None, description="Restrict to a specific accessibility batch_id"),
    jurisdiction_id: Optional[str] = Query(None, description="Optional jurisdiction_id filter"),
):
    """
    Latest successful-looking Lighthouse row for a website (matches URL with/without trailing slash).
    """
    variants = _url_variants(website_url)
    if not variants:
        raise HTTPException(status_code=400, detail="website_url is required")

    try:
        pool = await get_db_pool()
    except ValueError as e:
        logger.error(f"Lighthouse report: database not configured: {e}")
        raise HTTPException(status_code=503, detail="Database not configured") from e

    where_extra = ""
    params: List[Any] = [variants]
    idx = 2
    if batch_id:
        where_extra += f" AND batch_id = ${idx}"
        params.append(batch_id)
        idx += 1
    if jurisdiction_id:
        where_extra += f" AND jurisdiction_id = ${idx}"
        params.append(jurisdiction_id)
        idx += 1

    sql = f"""
        SELECT
            scan_key,
            batch_id,
            jurisdiction_id,
            website_url,
            final_url,
            scanned_at,
            status,
            lighthouse_version,
            score_accessibility,
            score_performance,
            score_best_practices,
            results
        FROM {BRONZE_LIGHTHOUSE}
        WHERE website_url = ANY($1::text[])
        {where_extra}
        ORDER BY scanned_at DESC NULLS LAST
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No Lighthouse audit found for this URL (run the lighthouse scan and persist to bronze).",
        )

    lhr = _lhr_from_row(row["results"])
    perf = _merge_score(row["score_performance"], lhr, "performance")
    acc = _merge_score(row["score_accessibility"], lhr, "accessibility")
    bp = _merge_score(row["score_best_practices"], lhr, "best-practices")
    seo = _category_score(lhr, "seo")

    scanned_at = row["scanned_at"]
    scanned_iso = scanned_at.isoformat() if scanned_at is not None else None

    requested = None
    if isinstance(lhr, dict):
        requested = lhr.get("requestedUrl") or lhr.get("finalUrl") or lhr.get("finalDisplayedUrl")
        if requested is not None:
            requested = str(requested)

    return LighthouseReportResponse(
        scan_key=str(row["scan_key"]),
        batch_id=str(row["batch_id"]),
        jurisdiction_id=str(row["jurisdiction_id"]),
        website_url=str(row["website_url"]),
        final_url=str(row["final_url"]) if row["final_url"] else None,
        scanned_at=scanned_iso,
        status=str(row["status"]),
        lighthouse_version=str(row["lighthouse_version"]) if row["lighthouse_version"] else None,
        requested_url=requested,
        scores=LighthouseScores(
            performance=perf,
            accessibility=acc,
            best_practices=bp,
            seo=seo,
        ),
        run_warnings=_warnings_from_lhr(lhr),
        screenshot_data_url=_extract_screenshot_data_url(lhr),
    )
