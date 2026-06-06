"""
Homepage "Story Lenses" endpoint, backed by public.item_interestingness.

Serves the homepage Story-Lenses feature: five fixed "lenses" (angles on civic
activity) plus a scoped activity strip, read directly from the already-modeled
public.item_interestingness serving table. NO transformation logic lives here —
the scoring (conflict / money / buried / interestingness_score) is produced
upstream in dbt; this endpoint only filters, orders, and shapes the rows for the
UI.

Patterns mirrored from decisions.py / search_postgres.py:
- asyncpg pool via get_db_pool() (the pool registers no JSON codec, so JSONB
  columns arrive as text — see _parse_json).
- normalize_state_input() for 2-letter / full-name state scoping.
- OpenTelemetry span around the query work.

WIRE-FORMAT RULE (CLAUDE.md): every stat/activity `value` is serialized as a
STRING so UI clients don't locale-format bare numbers (e.g. "2,024"). `date` is a
real DATE column -> serialized as an ISO "YYYY-MM-DD" string.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/api/lenses", tags=["lenses"])

tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------------------------
# Response models (inline, per spec — api/models.py is intentionally untouched).
# ---------------------------------------------------------------------------
class LensStat(BaseModel):
    """A single headline statistic on a lens card. `value` is ALWAYS a string."""
    value: str
    label: str
    tone: Optional[str] = None  # plain | green | amber | red | blue | purple


class LensCard(BaseModel):
    """One civic decision rendered as a story card within a lens."""
    headline: str
    stats: List[LensStat]
    jurisdiction: str
    date: Optional[str] = None          # occurred_at, ISO yyyy-mm-dd
    badge: Optional[str] = None         # lens label
    url: Optional[str] = None           # /decisions/{event_decision_id}
    state_code: Optional[str] = None
    state: Optional[str] = None


class Lens(BaseModel):
    """A named angle on civic activity; `placeholder` when it has no cards."""
    id: str
    label: str
    placeholder: bool
    cards: List[LensCard]


class ActivityCount(BaseModel):
    """One tile of the scoped activity strip. `value` is ALWAYS a string."""
    icon: str
    value: str
    label: str


class LensesResponse(BaseModel):
    """Full Story-Lenses payload for the homepage."""
    lenses: List[Lens]
    activity: List[ActivityCount]
    window: str
    location_label: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# window -> lookback days on occurred_at; "all" => no time filter.
_WINDOW_DAYS: Dict[str, Optional[int]] = {
    "week": 7,
    "month": 31,
    "quarter": 92,
    "year": 366,
    "all": None,
}

# Outcomes that mean "coming back" (tabled / deferred / postponed / continued /
# scheduled). Used by the `next` lens and the activity strip; kept in one place so
# the WHERE clause and the count stay in sync.
_COMING_BACK_RE = "(table|defer|postpon|continu|schedul)"

# Columns every lens query selects (superset needed to build any card/stat).
_CARD_COLS = """
    event_decision_id,
    title,
    summary,
    jurisdiction_name,
    state_code,
    state,
    city,
    occurred_at,
    outcome,
    primary_theme,
    conflict,
    money,
    buried,
    interestingness_score,
    votes_yes,
    votes_no,
    total_votes,
    competing_views_count,
    net_dollar_impact
"""


def _parse_json(value: Any) -> Any:
    """asyncpg returns JSONB as text without a codec; tolerate already-parsed."""
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


def money_fmt(value: Any) -> str:
    """
    Format a dollar amount compactly: $3.5B / $1.2M / $4.5K / $850.

    Returns a plain string (never a number — wire-format rule). Negative amounts
    keep their sign (e.g. -$1.2M). Returns "$0" for None / zero so callers that
    sum can always show a value. Scales through K/M/B/T — aggregate spending runs
    into the billions, so without B/T a $3.5B total would misformat as "$3544.9M".
    """
    if value is None:
        return "$0"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "$0"

    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)

    if magnitude >= 1_000_000_000_000:
        return f"{sign}${magnitude / 1_000_000_000_000:.1f}T"
    if magnitude >= 1_000_000_000:
        return f"{sign}${magnitude / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.1f}M"
    if magnitude >= 1_000:
        return f"{sign}${magnitude / 1_000:.1f}K"
    return f"{sign}${magnitude:.0f}"


def _iso_date(value: Any) -> Optional[str]:
    """Serialize a DATE to ISO yyyy-mm-dd (it may already be a date or a str)."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _jurisdiction_label(row: Any) -> str:
    """jurisdiction_name, falling back to 'City, ST' / city / state."""
    name = row["jurisdiction_name"]
    if name:
        return name
    city = row["city"]
    state_code = row["state_code"]
    if city and state_code:
        return f"{city}, {state_code}"
    return city or row["state"] or row["state_code"] or "Unknown"


def _headline(row: Any) -> str:
    """title, falling back to a trimmed summary."""
    title = row["title"]
    if title:
        return title
    summary = row["summary"]
    if summary:
        return summary[:120]
    return "Untitled decision"


# --- per-lens stat builders -------------------------------------------------
def _stats_contested(row: Any) -> List[LensStat]:
    stats: List[LensStat] = []
    if (row["total_votes"] or 0) > 0:
        stats.append(LensStat(value=f"{row['votes_yes']}–{row['votes_no']}", label="Vote"))
    if (row["competing_views_count"] or 0) > 0:
        stats.append(LensStat(value=str(row["competing_views_count"]), label="Opposing views", tone="amber"))
    if row["net_dollar_impact"]:  # skip None and exact 0 (no "$0" noise)
        stats.append(LensStat(value=money_fmt(row["net_dollar_impact"]), label="Impact", tone="green"))
    return stats[:3]


def _stats_money(row: Any) -> List[LensStat]:
    stats: List[LensStat] = []
    if row["net_dollar_impact"]:  # skip None and exact 0
        stats.append(LensStat(value=money_fmt(row["net_dollar_impact"]), label="Amount", tone="green"))
    if row["outcome"]:
        stats.append(LensStat(value=row["outcome"][:18], label="Outcome"))
    if row["primary_theme"]:
        stats.append(LensStat(value=row["primary_theme"][:18], label="Theme", tone="blue"))
    return stats[:3]


def _stats_next(row: Any) -> List[LensStat]:
    stats: List[LensStat] = []
    if row["outcome"]:
        stats.append(LensStat(value=row["outcome"][:18], label="Status", tone="amber"))
    if row["primary_theme"]:
        stats.append(LensStat(value=row["primary_theme"][:18], label="Theme", tone="blue"))
    if (row["total_votes"] or 0) > 0:
        stats.append(LensStat(value=f"{row['votes_yes']}–{row['votes_no']}", label="Last vote"))
    return stats[:3]


def _build_card(row: Any, label: str, stats: List[LensStat]) -> LensCard:
    return LensCard(
        headline=_headline(row),
        stats=stats,
        jurisdiction=_jurisdiction_label(row),
        date=_iso_date(row["occurred_at"]),
        badge=label,
        url=f"/decisions/{row['event_decision_id']}",
        state_code=row["state_code"],
        state=row["state"],
    )


def _build_flag_card(row: Any) -> LensCard:
    """
    Build a Raised-Eyebrows card from an item_flags row joined to its financial
    item. No `url`: the flag's source_record_url is /meetings/{id}, which has no
    frontend route yet, so we leave it unlinked (a 404 is worse than no link).
    """
    evidence = _parse_json(row["evidence"]) or {}
    pct = evidence.get("pct_below_limit")
    # Exact amount (not money_fmt) — rounding $49,991 to "$50.0K" would hide the
    # very "just under the limit" signal this lens is about.
    try:
        amount_str = f"${float(row['amount']):,.0f}"
    except (TypeError, ValueError):
        amount_str = money_fmt(row["amount"])
    stats: List[LensStat] = [LensStat(value=amount_str, label="Amount", tone="red")]
    if row["amount_type"]:
        stats.append(LensStat(value=str(row["amount_type"])[:18], label="Type", tone="amber"))
    if pct is not None:
        stats.append(LensStat(value=f"{pct}% under", label="Approval limit", tone="blue"))
    # Drill down to the flagged item's real meeting record. analysis_id is the
    # event_meeting_id; ?item highlights this specific line on the page.
    meeting_id = row["analysis_id"]
    fin_id = row["financial_item_id"]
    if meeting_id is not None:
        url = f"/meetings/{meeting_id}"
        if fin_id:
            url += f"?item={fin_id}"
    else:
        url = None
    return LensCard(
        headline=row["event_description"] or "Flagged financial item",
        stats=stats[:3],
        jurisdiction=row["jurisdiction_name"] or row["state_code"] or "Unknown",
        date=None,
        badge="Raised Eyebrows",
        url=url,
        state_code=row["state_code"],
        state=row["state"],
    )


# Lens definitions: (id, label, extra-WHERE template, ORDER BY). The location
# scope (state/city/window) is appended to __SCOPE__ at query time. flags/soon are
# handled out of band (item_flags empty; buried always 0 today) so they are not in
# this list.
_LENS_QUERY_DEFS = [
    ("contested", "Contested",
     "conflict > 0",
     "conflict DESC, interestingness_score DESC"),
    ("money", "Money Moves",
     "(money > 0 OR net_dollar_impact > 0)",
     "money DESC, interestingness_score DESC"),
    ("next", "Watch Next",
     f"outcome ~* '{_COMING_BACK_RE}'",
     "interestingness_score DESC"),
]

_STAT_BUILDERS = {
    "contested": _stats_contested,
    "money": _stats_money,
    "next": _stats_next,
}


def _build_scope(
    state_code: Optional[str],
    city: Optional[str],
    window_days: Optional[int],
) -> tuple[str, List[Any]]:
    """
    Build the shared scope predicate (state / city / window) and its params.

    Returns (sql_fragment, params). The fragment always starts with 'AND ...' or
    is empty, ready to splice after a lens-specific WHERE clause. Param order is
    fixed across all queries so callers can reuse the same list with a per-lens
    LIMIT appended.
    """
    clauses: List[str] = []
    params: List[Any] = []
    idx = 1

    if state_code:
        clauses.append(f"state_code = ${idx}")
        params.append(state_code)
        idx += 1

    if city and city.strip():
        clauses.append(f"(city ILIKE ${idx} OR jurisdiction_name ILIKE ${idx})")
        params.append(f"%{city.strip()}%")
        idx += 1

    if window_days is not None:
        # window -> cutoff on occurred_at; integer days interpolated from a fixed
        # server-side map (never user input), so no SQL injection surface.
        clauses.append(f"occurred_at >= current_date - {int(window_days)}")

    fragment = (" AND " + " AND ".join(clauses)) if clauses else ""
    return fragment, params


# Windows from narrowest to widest, for "auto" resolution.
_ORDERED_WINDOWS = ["week", "month", "quarter", "year", "all"]


async def _resolve_auto_window(
    conn: Any,
    state_code: Optional[str],
    city: Optional[str],
    min_items: int,
) -> str:
    """
    Pick the narrowest window whose total decisions in scope reaches `min_items`.

    Counts decisions for the location (ignoring time) bucketed by each window in a
    single query, then returns the smallest window that clears the threshold,
    falling back to "all" when even all-time has fewer than `min_items`. This keeps
    the homepage feed populated for small places without forcing the user to widen
    the grain by hand.
    """
    loc_sql, loc_params = _build_scope(state_code, city, None)
    sql = f"""
        SELECT
            COUNT(*) FILTER (WHERE occurred_at >= current_date - 7)   AS w_week,
            COUNT(*) FILTER (WHERE occurred_at >= current_date - 31)  AS w_month,
            COUNT(*) FILTER (WHERE occurred_at >= current_date - 92)  AS w_quarter,
            COUNT(*) FILTER (WHERE occurred_at >= current_date - 366) AS w_year,
            COUNT(*)                                                  AS w_all
        FROM item_interestingness
        WHERE TRUE{loc_sql}
    """
    row = await conn.fetchrow(sql, *loc_params)
    counts = {
        "week": int(row["w_week"]),
        "month": int(row["w_month"]),
        "quarter": int(row["w_quarter"]),
        "year": int(row["w_year"]),
        "all": int(row["w_all"]),
    }
    for window in _ORDERED_WINDOWS:
        if counts[window] >= min_items:
            return window
    return "all"


@router.get("", response_model=LensesResponse)
async def get_lenses(
    state: Optional[str] = Query(
        None, description="2-letter code or full state name (normalized)",
    ),
    city: Optional[str] = Query(
        None, description="City name (ILIKE on city / jurisdiction_name)",
    ),
    window: str = Query(
        "auto",
        description="Lookback window: auto | week | month | quarter | year | all. "
                    "'auto' picks the narrowest window with >= min_items decisions.",
    ),
    min_items: int = Query(
        10, ge=1, le=100,
        description="Target decision count used to resolve window='auto' (default 10)",
    ),
    limit_per_lens: int = Query(
        6, ge=1, le=20, description="Max cards per lens (1..20, default 6)",
    ),
) -> LensesResponse:
    """
    Homepage Story-Lenses, scoped by state / city / time window.

    Returns all five lenses in a fixed order — contested, money, flags, soon,
    next — each with up to `limit_per_lens` cards, plus a 4-tile activity strip
    scoped to the same filters. Lenses with no cards come back `placeholder: true`
    so the frontend can show an honest empty state.

    `window='auto'` (the default) resolves server-side to the narrowest grain that
    surfaces at least `min_items` decisions for the location, so small places still
    get a populated feed; the resolved grain is returned in `window`.

    Example::

        GET /api/lenses?state=AL&city=Tuscaloosa&window=auto&limit_per_lens=6
    """
    requested_window = (window or "auto").lower()
    if requested_window != "auto" and requested_window not in _WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"window must be 'auto' or one of {sorted(_WINDOW_DAYS)} "
                   f"(got '{requested_window}')",
        )
    state_code = normalize_state_input(state)

    with tracer.start_as_current_span("lenses") as span:
        span.set_attribute("lenses.state_code", state_code or "")
        span.set_attribute("lenses.city", city or "")
        span.set_attribute("lenses.window_requested", requested_window)
        span.set_attribute("lenses.limit_per_lens", limit_per_lens)

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Resolve 'auto' to a concrete grain before building any scope.
                if requested_window == "auto":
                    window = await _resolve_auto_window(conn, state_code, city, min_items)
                else:
                    window = requested_window
                window_days = _WINDOW_DAYS[window]
                span.set_attribute("lenses.window", window)

                scope_sql, scope_params = _build_scope(state_code, city, window_days)
                # The LIMIT placeholder is one past the scope params (same per lens).
                limit_idx = len(scope_params) + 1

                lenses: List[Lens] = []

                with tracer.start_as_current_span("lenses.query") as qspan:
                    # The three data-backed lenses.
                    for lens_id, label, where_tpl, order_by in _LENS_QUERY_DEFS:
                        sql = f"""
                            SELECT {_CARD_COLS}
                            FROM item_interestingness
                            WHERE {where_tpl}{scope_sql}
                            ORDER BY {order_by}
                            LIMIT ${limit_idx}
                        """
                        rows = await conn.fetch(sql, *scope_params, limit_per_lens)
                        builder = _STAT_BUILDERS[lens_id]
                        cards = [_build_card(r, label, builder(r)) for r in rows]
                        lenses.append(Lens(
                            id=lens_id,
                            label=label,
                            placeholder=len(cards) == 0,
                            cards=cards,
                        ))

                    # Activity strip — computed once over the same scope. The
                    # leading WHERE TRUE lets the scope fragment (AND ...) splice in
                    # cleanly even when no filters are set.
                    activity_sql = f"""
                        SELECT
                            COUNT(*) FILTER (WHERE conflict > 0) AS contested_count,
                            COALESCE(
                                SUM(net_dollar_impact) FILTER (WHERE money > 0), 0
                            ) AS tracked_spending,
                            COUNT(*) AS total_decisions,
                            COUNT(*) FILTER (
                                WHERE outcome ~* '{_COMING_BACK_RE}'
                            ) AS coming_back_count
                        FROM item_interestingness
                        WHERE TRUE{scope_sql}
                    """
                    agg = await conn.fetchrow(activity_sql, *scope_params)
                    qspan.set_attribute(
                        "lenses.total_decisions", int(agg["total_decisions"])
                    )

                    # Raised Eyebrows (flags) — item_flags joined to its financial
                    # item for display fields. Anomalies are NOT time-bound, so this
                    # is location-scoped only (no window filter).
                    flag_clauses: List[str] = []
                    flag_params: List[Any] = []
                    fidx = 1
                    if state_code:
                        flag_clauses.append(f"fi.state_code = ${fidx}")
                        flag_params.append(state_code)
                        fidx += 1
                    if city and city.strip():
                        flag_clauses.append(f"fi.jurisdiction_name ILIKE ${fidx}")
                        flag_params.append(f"%{city.strip()}%")
                        fidx += 1
                    flag_where = (" AND " + " AND ".join(flag_clauses)) if flag_clauses else ""
                    # Drill down to the flagged item's real MEETING record
                    # (/meetings/{event_meeting_id}), which lists the meeting's
                    # decisions + financial items and highlights this one via ?item.
                    # analysis_id IS the event_meeting_id (FK). Every flag has one, so
                    # every flag is a working drilldown — no fake slug, no mislink.
                    flag_sql = f"""
                        SELECT
                            fi.event_description, fi.jurisdiction_name,
                            fi.state_code, fi.state, fi.amount, fi.amount_type,
                            f.severity, f.evidence, f.anomaly_score,
                            fi.analysis_id, fi.financial_item_id
                        FROM item_flags f
                        JOIN event_financial_item fi
                          ON fi.event_financial_item_id = f.subject_ref
                        WHERE TRUE{flag_where}
                        ORDER BY f.anomaly_score DESC NULLS LAST
                        LIMIT ${fidx}
                    """
                    flag_rows = await conn.fetch(flag_sql, *flag_params, limit_per_lens)
                    flags_lens = Lens(
                        id="flags",
                        label="Raised Eyebrows",
                        placeholder=len(flag_rows) == 0,
                        cards=[_build_flag_card(r) for r in flag_rows],
                    )

        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — surface a clean 500
            span.record_exception(e)
            logger.error("Lenses query failed: {}", e)
            raise HTTPException(status_code=500, detail="Failed to load lenses")

        # flags lens (Raised Eyebrows) is built inside the query block above from
        # item_flags. soon lens: buried > 0 never matches today -> empty placeholder.
        soon_lens = Lens(id="soon", label="Moving Fast", placeholder=True, cards=[])

        # Fixed order: contested, money, flags, soon, next.
        by_id = {lens.id: lens for lens in lenses}
        ordered_lenses = [
            by_id["contested"],
            by_id["money"],
            flags_lens,
            soon_lens,
            by_id["next"],
        ]

        # Activity strip — every value serialized as a string (wire-format rule).
        activity = [
            ActivityCount(
                icon="\U0001F525",  # 🔥
                value=str(int(agg["contested_count"])),
                label="contested decisions",
            ),
            ActivityCount(
                icon="\U0001F4B2",  # 💲
                value=money_fmt(agg["tracked_spending"]),
                label="in tracked spending",
            ),
            ActivityCount(
                icon="\U0001F5F3️",  # 🗳️
                value=str(int(agg["total_decisions"])),
                label="decisions analyzed",
            ),
            ActivityCount(
                icon="\U0001F4C5",  # 📅
                value=str(int(agg["coming_back_count"])),
                label="coming back for a vote",
            ),
        ]

        # location_label for the UI header.
        if city and city.strip() and state_code:
            location_label = f"{city.strip()}, {state_code}"
        elif state_code:
            location_label = state_code
        elif city and city.strip():
            location_label = city.strip()
        else:
            location_label = None

        span.set_attribute(
            "lenses.card_total", sum(len(l.cards) for l in ordered_lenses)
        )
        logger.info(
            "🔭 Lenses -> {} cards (state={}, city={}, window={})",
            sum(len(l.cards) for l in ordered_lenses), state_code, city, window,
        )

        return LensesResponse(
            lenses=ordered_lenses,
            activity=activity,
            window=window,
            location_label=location_label,
        )
