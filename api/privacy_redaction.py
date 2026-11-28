"""Serve-time name redaction for meeting text (#1468).

Every endpoint that returns verbatim meeting text (transcript excerpts, public-comment quotes, search snippets,
decision statements, agenda passages) passes its response through ``redact_response`` before returning it. The
rewrite itself is ``core_lib.privacy.NameRedactor``: a probable private person's full name becomes "First L.", a
home address after "I live at" / "of <number> <street>" becomes "[address]", and ``<mark>`` highlighting survives.

Officials keep their names. They are loaded once an hour from the served tables: ``person_government`` (local
officials keyed by their government, state-level officials keyed by state) and ``body_membership`` (members of a
governing body, keyed by its jurisdiction). When the tables can't be read the redactor runs with no officials, which
shortens more names, never fewer.

Context: each object in the response that carries a text field is redacted with the officials of that object's own
``state_code`` and jurisdiction (``jurisdiction_name`` / ``jurisdiction``); a nested object inherits its parent's.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Iterable, Optional

from loguru import logger
from pydantic import BaseModel

from core_lib.privacy import default_redactor, is_school_board, official_name_key, place_key, shorten_full_name

# Response fields that carry verbatim meeting text.
TEXT_FIELDS: frozenset[str] = frozenset(
    {
        "excerpt",
        "quote",
        "quote_highlighted",
        "evidence",
        "evidence_passage",
        "matched_text",
        "match_text",
        "detail",
        "meeting_summary",
        "agenda_summary",
        "decision_statement",
        "decision_headline",
        "shape_cue_text",
        "corrected_summary",
        "text",
        "answer",
        "company_evidence",
    }
)
# Fields that hold one person's name taken from a transcript (not a roster): shortened to "First L." unless an
# official of that place.
NAME_FIELDS: frozenset[str] = frozenset({"speaker_name", "possible_name"})

# Search results and decision cards put the snippet in ``description`` and AI text in ``headline``/``title``; those
# endpoints pass these too.
SNIPPET_FIELDS: frozenset[str] = TEXT_FIELDS | {"description", "headline", "title", "summary"}

# A decision's AI-written JSON blobs and parsed agenda/minutes: every string inside is redacted.
DECISION_JSON_FIELDS: frozenset[str] = frozenset({"human_element", "competing_views", "smart_brevity", "meeting_record"})

_STATE_KEYS = ("state_code", "state")
_JURIS_KEYS = ("jurisdiction_name", "jurisdiction", "decision_jurisdiction", "match_place")

_TTL_S = 3600.0
_RETRY_S = 300.0
_LOAD_TIMEOUT_S = 5.0

_cache: dict[str, Any] = {"at": 0.0, "ok": False, "by_place": {}, "by_state": {}}
_lock = asyncio.Lock()

OFFICIALS_SQL = """
select state_code, jurisdiction, full_name, office from person_government
where full_name is not null and coalesce(is_current, true)
"""
MEMBERS_SQL = """
select j.state_code, j.name as jurisdiction, b.member_name as full_name
from body_membership b join jurisdictions j on j.jurisdiction_id = b.jurisdiction_id
where b.member_name is not null and coalesce(b.is_current, true)
"""


def build_official_index(
    official_rows: Iterable[Any], member_rows: Iterable[Any] = ()
) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """({place_key: name keys}, {state_code: name keys of state-level officials})."""
    by_place: dict[str, set[str]] = {}
    by_state: dict[str, set[str]] = {}
    for r in official_rows:
        key = official_name_key(r["full_name"] or "")
        if not key:
            continue
        if (r.get("office") if isinstance(r, dict) else r["office"]) == "government":
            pk = place_key(r["state_code"], r["jurisdiction"])
            if pk:
                by_place.setdefault(pk, set()).add(key)
        elif r["state_code"]:
            by_state.setdefault(str(r["state_code"]).upper(), set()).add(key)
    for r in member_rows:
        key = official_name_key(r["full_name"] or "")
        pk = place_key(r["state_code"], r["jurisdiction"])
        if key and pk:
            by_place.setdefault(pk, set()).add(key)
    return ({k: frozenset(v) for k, v in by_place.items()}, {k: frozenset(v) for k, v in by_state.items()})


async def _load() -> None:
    # Its own short-lived connection, not the shared pool: an hourly read, and never a pool tied to another loop.
    import asyncpg

    from api.database import DATA_SEARCH_PATH
    from api.routes.search_postgres import DATABASE_URL

    if not DATABASE_URL:
        raise RuntimeError("no database configured")
    conn = await asyncpg.connect(DATABASE_URL, server_settings={"search_path": DATA_SEARCH_PATH})
    try:
        officials = [dict(r) for r in await conn.fetch(OFFICIALS_SQL)]
        try:
            members = [dict(r) for r in await conn.fetch(MEMBERS_SQL)]
        except Exception as e:  # body_membership is newer than person_government
            logger.warning("redaction: body_membership unavailable ({}); local officials only", e)
            members = []
    finally:
        await conn.close()
    by_place, by_state = build_official_index(officials, members)
    _cache.update(at=time.monotonic(), ok=True, by_place=by_place, by_state=by_state)
    logger.info("redaction: {:,} governments and {:,} states of officials loaded", len(by_place), len(by_state))


async def ensure_officials() -> None:
    """Load (or refresh) the officials index; on failure keep what we have and retry in a few minutes."""
    age = time.monotonic() - _cache["at"]
    if _cache["ok"] and age < _TTL_S or (not _cache["ok"] and _cache["at"] and age < _RETRY_S):
        return
    async with _lock:
        age = time.monotonic() - _cache["at"]
        if _cache["ok"] and age < _TTL_S or (not _cache["ok"] and _cache["at"] and age < _RETRY_S):
            return
        try:
            await asyncio.wait_for(_load(), timeout=_LOAD_TIMEOUT_S)
        except Exception as e:
            logger.warning("redaction: officials not loaded ({}); every name is shortened", e)
            _cache.update(at=time.monotonic(), ok=False)


def officials_for(state_code: Optional[str], jurisdiction: Optional[str]) -> frozenset[str]:
    """Name keys kept as said for text from this place: its government's officials and its state's."""
    out: set[str] = set()
    if state_code:
        out |= _cache["by_state"].get(str(state_code).upper(), frozenset())
        pk = place_key(state_code, jurisdiction)
        if pk:
            out |= _cache["by_place"].get(pk, frozenset())
    return frozenset(out)


def redact_text(
    text: Optional[str],
    state_code: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    school: Optional[bool] = None,
) -> Optional[str]:
    """One served string. ``school`` (default: the jurisdiction's name says school board) masks every private name
    as ``[name]``, because a resident at a school board may be a student."""
    if not text or not isinstance(text, str):
        return text
    if school is None:
        school = is_school_board(jurisdiction)
    return default_redactor().redact(text, official_names=officials_for(state_code, jurisdiction), school=school)


def shorten_name(
    name: Optional[str],
    state_code: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    school: Optional[bool] = None,
) -> Optional[str]:
    if school is None:
        school = is_school_board(jurisdiction)
    official_names = officials_for(state_code, jurisdiction)
    if school and name and shorten_full_name(name, official_names=official_names) != name:
        return "[name]"
    return shorten_full_name(name, official_names=official_names)


Ctx = tuple[Optional[str], Optional[str], bool]
_SCHOOL_KEYS = ("jurisdiction_type", "meeting_title", "event_title", "body_name")


def _redact_value(
    key: str, v: str, fields: frozenset[str], ctx: Ctx, deep: bool,
    name_fields: frozenset[str],
) -> str:
    if key in name_fields:
        return shorten_name(v, *ctx) or v
    if deep or key in fields:
        return redact_text(v, *ctx) or v
    return v


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _context(obj: Any, inherited: Ctx) -> Ctx:
    state, juris, school = inherited
    meta = _get(obj, "metadata")
    sources = [obj] + ([meta] if isinstance(meta, dict) else [])
    for src in sources:
        for k in _STATE_KEYS:
            v = _get(src, k)
            if isinstance(v, str) and len(v) == 2:
                state = v
                break
        for k in _JURIS_KEYS:
            v = _get(src, k)
            if isinstance(v, str) and v:
                juris = v
                break
        school = school or is_school_board(juris, *(_get(src, k) for k in _SCHOOL_KEYS))
    return state, juris, school


def redact_payload(
    payload: Any,
    fields: frozenset[str] = TEXT_FIELDS,
    _ctx: Ctx = (None, None, False),
    *,
    deep_fields: frozenset[str] = frozenset(),
    name_fields: frozenset[str] = NAME_FIELDS,
    _deep: bool = False,
) -> Any:
    """Redact, in place, every string in ``fields`` anywhere in ``payload`` (dicts, lists, pydantic models).

    ``NAME_FIELDS`` are shortened as names. Under a key in ``deep_fields`` (a JSON blob such as a decision's
    ``competing_views``) every string is redacted, whatever its key.
    """
    if isinstance(payload, list):
        for i, item in enumerate(payload):
            if isinstance(item, str) and _deep:
                payload[i] = redact_text(item, *_ctx) or item
            else:
                redact_payload(item, fields, _ctx, deep_fields=deep_fields, name_fields=name_fields, _deep=_deep)
        return payload
    if isinstance(payload, BaseModel):
        ctx = _context(payload, _ctx)
        for name in type(payload).model_fields:
            v = getattr(payload, name, None)
            deep = _deep or name in deep_fields
            if isinstance(v, str):
                new = _redact_value(name, v, fields, ctx, deep, name_fields)
                if new is not v:
                    setattr(payload, name, new)
            elif isinstance(v, (list, dict, BaseModel)):
                redact_payload(v, fields, ctx, deep_fields=deep_fields, name_fields=name_fields, _deep=deep)
        return payload
    if isinstance(payload, dict):
        ctx = _context(payload, _ctx)
        for k, v in list(payload.items()):
            deep = _deep or k in deep_fields
            if isinstance(v, str):
                payload[k] = _redact_value(k, v, fields, ctx, deep, name_fields)
            elif isinstance(v, (list, dict, BaseModel)):
                redact_payload(v, fields, ctx, deep_fields=deep_fields, name_fields=name_fields, _deep=deep)
        return payload
    return payload


async def redact_response(
    payload: Any,
    fields: frozenset[str] = TEXT_FIELDS,
    *,
    deep_fields: frozenset[str] = frozenset(),
    name_fields: frozenset[str] = NAME_FIELDS,
    state_code: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> Any:
    """``redact_payload`` after making sure the officials index is loaded. Returns ``payload``.

    ``state_code``/``jurisdiction`` give the place when the payload itself doesn't carry one. Pass
    ``name_fields=frozenset()`` when name fields were already shortened with their place (job claims)."""
    await ensure_officials()
    ctx: Ctx = (state_code, jurisdiction, is_school_board(jurisdiction))
    return redact_payload(payload, fields, ctx, deep_fields=deep_fields, name_fields=name_fields)
