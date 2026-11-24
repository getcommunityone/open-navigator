"""Stance responses (#851): "Where Do You Stand?" agree / disagree / not sure answers.

    GET  /api/stance/packs
    GET  /api/stance/packs/{pack_id}
    POST /api/stance/responses
    GET  /api/stance/packs/{pack_id}/results

Anonymous play: a random browser UUID, no login. No IP, name or other personal
data is stored; the rate-limit key is a hash kept only in memory. Group splits
are withheld below ``STANCE_MIN_SAMPLE`` answers. No count is ever seeded or
estimated: an empty table reports ``n = 0`` for every group.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import STATE_NAME_TO_CODE, get_db_pool

router = APIRouter(prefix="/stance", tags=["stance"])
tracer = trace.get_tracer(__name__)

PACKS_DIR = Path(__file__).resolve().parents[1] / "stance_packs"
ALLOWED_CHARTS = frozenset(
    {
        "job-claims",
        "sites",
        "agenda-items",
        "concerns",
        "meeting-mentions",
        "community-events",
        "projects",
    }
)
MAX_PLACE_LEN = 120
_STATE_CODE_TO_NAME: dict[str, str] = {c: n for n, c in STATE_NAME_TO_CODE.items()}


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw not in (None, "") else default
    except ValueError:
        value = default
    return max(minimum, value)


MIN_SAMPLE = _int_env("STANCE_MIN_SAMPLE", 30, 1)
_RATE_PER_HOUR = _int_env("STANCE_RATE_PER_HOUR", 120, 1)
_HOUR = 3600.0
_MAX_TRACKED_VISITORS = 4096
_visitor_timestamps: dict[str, list[float]] = {}


# --------------------------------------------------------------------------
# Pack loading / validation
# --------------------------------------------------------------------------


class PackError(ValueError):
    """A stance pack file is malformed."""


_REQUIRED_STATEMENT_FIELDS = (
    "statement_id",
    "version",
    "order",
    "category",
    "statement",
    "chart",
)


def validate_pack(pack: dict[str, Any], source: str = "pack") -> dict[str, Any]:
    for key in ("pack_id", "title", "version", "statements"):
        if key not in pack:
            raise PackError(f"{source}: missing '{key}'")
    if not isinstance(pack["version"], int) or isinstance(pack["version"], bool):
        raise PackError(f"{source}: 'version' must be an integer")
    statements = pack["statements"]
    if not isinstance(statements, list) or not statements:
        raise PackError(f"{source}: 'statements' must be a non-empty list")
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    for st in statements:
        for key in _REQUIRED_STATEMENT_FIELDS:
            if key not in st or st[key] in (None, ""):
                raise PackError(f"{source}: statement missing '{key}'")
        if not isinstance(st["version"], int) or not isinstance(st["order"], int):
            raise PackError(f"{source}: version and order must be integers")
        if st["statement_id"] in seen_ids:
            raise PackError(f"{source}: duplicate statement_id {st['statement_id']}")
        if st["order"] in seen_orders:
            raise PackError(f"{source}: duplicate order {st['order']}")
        seen_ids.add(st["statement_id"])
        seen_orders.add(st["order"])
    pack["statements"] = sorted(statements, key=lambda s: s["order"])
    return pack


def load_packs(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load and validate every ``*.json`` pack in ``directory``, keyed by pack_id."""
    packs: dict[str, dict[str, Any]] = {}
    for path in sorted((directory or PACKS_DIR).glob("*.json")):
        pack = validate_pack(json.loads(path.read_text(encoding="utf-8")), path.name)
        if pack["pack_id"] in packs:
            raise PackError(f"duplicate pack_id {pack['pack_id']}")
        packs[pack["pack_id"]] = pack
    return packs


PACKS: dict[str, dict[str, Any]] = load_packs()


def get_pack(pack_id: str) -> dict[str, Any]:
    pack = PACKS.get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Unknown pack")
    return pack


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------


class PackSummary(BaseModel):
    pack_id: str
    title: str
    version: int
    statement_count: int


class StanceResponseIn(BaseModel):
    player_id: uuid.UUID
    pack_id: str
    statement_id: str
    answer: Literal["agree", "disagree", "unsure"]
    state_code: str | None = None
    place_name: str | None = None


class StanceResponseOut(BaseModel):
    pack_id: str
    statement_id: str
    statement_version: int
    answer: str
    state_code: str | None = None
    state: str | None = None
    place_name: str | None = None


class GroupResult(BaseModel):
    available: bool
    n: int
    agree: int | None = None
    disagree: int | None = None
    unsure: int | None = None


class StatementResults(BaseModel):
    statement_id: str
    statement_version: int
    your_answer: str | None = None
    national: GroupResult
    state: GroupResult | None = None
    place: GroupResult | None = None


class PackResults(BaseModel):
    min_sample: int
    statements: list[StatementResults]


class PostResponseOut(BaseModel):
    stance_response: StanceResponseOut
    results: StatementResults


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.stance_response (
    stance_response_id bigserial PRIMARY KEY,
    player_id          uuid        NOT NULL,
    pack_id            text        NOT NULL,
    statement_id       text        NOT NULL,
    statement_version  integer     NOT NULL,
    answer             text        NOT NULL CHECK (answer IN ('agree','disagree','unsure')),
    state_code         char(2),
    state              text,
    place_name         text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (player_id, pack_id, statement_id)
)
"""
CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS stance_response_pack_statement_state_idx "
    "ON public.stance_response (pack_id, statement_id, state_code)"
)

UPSERT_SQL = """
INSERT INTO public.stance_response
    (player_id, pack_id, statement_id, statement_version, answer, state_code, state, place_name)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (player_id, pack_id, statement_id) DO UPDATE SET
    statement_version = EXCLUDED.statement_version,
    answer            = EXCLUDED.answer,
    state_code        = EXCLUDED.state_code,
    state             = EXCLUDED.state,
    place_name        = EXCLUDED.place_name,
    updated_at        = now()
RETURNING pack_id, statement_id, statement_version, answer, state_code, state, place_name
"""

# One grouped query for the whole pack. $1 pack, $2 statement ids, $3 their current
# versions (parallel arrays), $4 state_code (or NULL), $5 lowercase trimmed place (or NULL).
# One row per statement that has at least one current-version answer.
RESULTS_SQL = """
WITH current AS (
    SELECT s.statement_id, v.version
    FROM unnest($2::text[]) WITH ORDINALITY AS s(statement_id, ord)
    JOIN unnest($3::int[]) WITH ORDINALITY AS v(version, ord) USING (ord)
)
SELECT
    r.statement_id,
    count(*)                                                      AS nat_n,
    count(*) FILTER (WHERE r.answer = 'agree')                    AS nat_agree,
    count(*) FILTER (WHERE r.answer = 'disagree')                 AS nat_disagree,
    count(*) FILTER (WHERE r.answer = 'unsure')                   AS nat_unsure,
    count(*) FILTER (WHERE r.state_code = $4::text)               AS st_n,
    count(*) FILTER (WHERE r.state_code = $4::text AND r.answer = 'agree')    AS st_agree,
    count(*) FILTER (WHERE r.state_code = $4::text AND r.answer = 'disagree') AS st_disagree,
    count(*) FILTER (WHERE r.state_code = $4::text AND r.answer = 'unsure')   AS st_unsure,
    count(*) FILTER (WHERE r.state_code = $4::text
                       AND lower(btrim(r.place_name)) = $5::text) AS pl_n,
    count(*) FILTER (WHERE r.state_code = $4::text AND lower(btrim(r.place_name)) = $5::text
                       AND r.answer = 'agree')                    AS pl_agree,
    count(*) FILTER (WHERE r.state_code = $4::text AND lower(btrim(r.place_name)) = $5::text
                       AND r.answer = 'disagree')                 AS pl_disagree,
    count(*) FILTER (WHERE r.state_code = $4::text AND lower(btrim(r.place_name)) = $5::text
                       AND r.answer = 'unsure')                   AS pl_unsure
FROM public.stance_response r
JOIN current c ON c.statement_id = r.statement_id AND c.version = r.statement_version
WHERE r.pack_id = $1
GROUP BY r.statement_id
"""

YOURS_SQL = """
SELECT statement_id, answer FROM public.stance_response
WHERE player_id = $1 AND pack_id = $2
"""

_table_ready = False


async def _ensure_table(conn: Any) -> None:
    global _table_ready
    if _table_ready:
        return
    await conn.execute(CREATE_TABLE_SQL)
    await conn.execute(CREATE_INDEX_SQL)
    _table_ready = True


def reset_table_ready() -> None:
    global _table_ready
    _table_ready = False


# --------------------------------------------------------------------------
# Rate limit (in memory only; the key is a hash and is never stored or logged)
# --------------------------------------------------------------------------


def _visitor_key(request: Request, player_id: uuid.UUID) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
        request.client.host if request.client else "unknown"
    )
    return hashlib.sha256(f"{ip}|{player_id}".encode()).hexdigest()[:32]


def _check_rate_limit(visitor: str) -> None:
    now = time.monotonic()
    if (
        len(_visitor_timestamps) >= _MAX_TRACKED_VISITORS
        and visitor not in _visitor_timestamps
    ):
        for k in [
            k
            for k, ts in _visitor_timestamps.items()
            if not ts or now - ts[-1] >= _HOUR
        ]:
            _visitor_timestamps.pop(k, None)
    history = [t for t in _visitor_timestamps.get(visitor, []) if now - t < _HOUR]
    if len(history) >= _RATE_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many answers. Try again later.",
        )
    history.append(now)
    _visitor_timestamps[visitor] = history


def clear_stance_rate_limits() -> None:
    _visitor_timestamps.clear()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _normalize_state(state_code: str | None) -> tuple[str | None, str | None]:
    if state_code is None or not state_code.strip():
        return None, None
    code = state_code.strip().upper()
    name = _STATE_CODE_TO_NAME.get(code)
    if name is None:
        raise HTTPException(status_code=400, detail="Unknown state_code")
    return code, name


def _normalize_place(place_name: str | None) -> str | None:
    if place_name is None:
        return None
    place = place_name.strip()
    if not place:
        return None
    if len(place) > MAX_PLACE_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"place_name is longer than {MAX_PLACE_LEN} characters",
        )
    return place


def _group(row: Any, prefix: str) -> GroupResult:
    n = int(row[f"{prefix}_n"]) if row is not None else 0
    if row is None or n < MIN_SAMPLE:
        return GroupResult(available=False, n=n)
    return GroupResult(
        available=True,
        n=n,
        agree=int(row[f"{prefix}_agree"]),
        disagree=int(row[f"{prefix}_disagree"]),
        unsure=int(row[f"{prefix}_unsure"]),
    )


def _shape_results(
    pack: dict[str, Any],
    rows: list[Any],
    yours: dict[str, str],
    *,
    has_state: bool,
    has_place: bool,
    only: str | None = None,
) -> list[StatementResults]:
    by_id = {r["statement_id"]: r for r in rows}
    out: list[StatementResults] = []
    for st in pack["statements"]:
        if only is not None and st["statement_id"] != only:
            continue
        row = by_id.get(st["statement_id"])
        out.append(
            StatementResults(
                statement_id=st["statement_id"],
                statement_version=st["version"],
                your_answer=yours.get(st["statement_id"]),
                national=_group(row, "nat"),
                state=_group(row, "st") if has_state else None,
                place=_group(row, "pl") if has_place else None,
            )
        )
    return out


async def _fetch_results(
    conn: Any,
    pack: dict[str, Any],
    state_code: str | None,
    place: str | None,
    player_id: uuid.UUID | None,
    only: str | None = None,
) -> list[StatementResults]:
    ids = [s["statement_id"] for s in pack["statements"]]
    versions = [s["version"] for s in pack["statements"]]
    place_key = place.lower() if (place and state_code) else None
    rows = await conn.fetch(
        RESULTS_SQL, pack["pack_id"], ids, versions, state_code, place_key
    )
    yours: dict[str, str] = {}
    if player_id is not None:
        for r in await conn.fetch(YOURS_SQL, player_id, pack["pack_id"]):
            yours[r["statement_id"]] = r["answer"]
    return _shape_results(
        pack,
        list(rows),
        yours,
        has_state=state_code is not None,
        has_place=place_key is not None,
        only=only,
    )


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("/packs", response_model=list[PackSummary])
async def list_packs() -> list[PackSummary]:
    with tracer.start_as_current_span("stance.list_packs"):
        return [
            PackSummary(
                pack_id=p["pack_id"],
                title=p["title"],
                version=p["version"],
                statement_count=len(p["statements"]),
            )
            for p in PACKS.values()
        ]


@router.get("/packs/{pack_id}")
async def get_pack_content(pack_id: str) -> dict[str, Any]:
    with tracer.start_as_current_span("stance.get_pack") as span:
        span.set_attribute("stance.pack_id", pack_id)
        return get_pack(pack_id)


@router.post("/responses", response_model=PostResponseOut)
async def post_response(body: StanceResponseIn, request: Request) -> PostResponseOut:
    with tracer.start_as_current_span("stance.post_response") as span:
        pack = get_pack(body.pack_id)
        statement = next(
            (s for s in pack["statements"] if s["statement_id"] == body.statement_id),
            None,
        )
        if statement is None:
            raise HTTPException(status_code=404, detail="Unknown statement")
        state_code, state = _normalize_state(body.state_code)
        place = _normalize_place(body.place_name)
        if place is not None and state_code is None:
            raise HTTPException(status_code=400, detail="place_name needs a state_code")
        span.set_attribute("stance.pack_id", body.pack_id)
        span.set_attribute("stance.statement_id", body.statement_id)
        _check_rate_limit(_visitor_key(request, body.player_id))

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            row = await conn.fetchrow(
                UPSERT_SQL,
                body.player_id,
                body.pack_id,
                body.statement_id,
                statement["version"],
                body.answer,
                state_code,
                state,
                place,
            )
            results = await _fetch_results(
                conn, pack, state_code, place, body.player_id, only=body.statement_id
            )
        logger.info(
            "stance answer stored pack={} statement={}", body.pack_id, body.statement_id
        )
        saved = StanceResponseOut(
            pack_id=row["pack_id"],
            statement_id=row["statement_id"],
            statement_version=row["statement_version"],
            answer=row["answer"],
            state_code=row["state_code"],
            state=row["state"],
            place_name=row["place_name"],
        )
        return PostResponseOut(stance_response=saved, results=results[0])


@router.get("/packs/{pack_id}/results", response_model=PackResults)
async def pack_results(
    pack_id: str,
    state_code: Annotated[str | None, Query()] = None,
    place_name: Annotated[str | None, Query()] = None,
    player_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PackResults:
    with tracer.start_as_current_span("stance.pack_results") as span:
        pack = get_pack(pack_id)
        code, _ = _normalize_state(state_code)
        place = _normalize_place(place_name)
        if place is not None and code is None:
            raise HTTPException(status_code=400, detail="place_name needs a state_code")
        span.set_attribute("stance.pack_id", pack_id)
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await _ensure_table(conn)
            statements = await _fetch_results(conn, pack, code, place, player_id)
        logger.info("stance results pack={} statements={}", pack_id, len(statements))
        return PackResults(min_sample=MIN_SAMPLE, statements=statements)
