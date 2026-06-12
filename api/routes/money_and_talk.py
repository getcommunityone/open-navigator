"""
"Money vs. talk" by theme — GET /api/money-and-talk.

Pairs how much a theme is DISCUSSED (decision_count = "talk") against how much
money it actually MOVES (spend_amount = "money"), per CLAUDE.md's no-fabricated-
data rule: spend_amount can legitimately be 0 for talk-heavy themes, and we
return 0.0 there rather than inventing a budget figure.

Source: public.topic_money_and_talk (grain = jurisdiction × canonical_theme ×
month), resolved unqualified via the connection search_path (public in dev /
gold in prod), matching the other serving routes. Aggregates roll up across
jurisdictions and months for the requested filter, with a per-theme monthly
series returned alongside (sparse — only months that actually have rows).

Money is the net dollar impact of money-flagged decisions, NOT a government
budget — surfaced verbatim in the `note` field.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/api/money-and-talk", tags=["money-and-talk"])
tracer = trace.get_tracer(__name__)

_NOTE = (
    "Money reflects the net dollar impact of money-flagged decisions, "
    "not a government budget."
)


class MonthlyPoint(BaseModel):
    month: str  # "YYYY-MM"
    decision_count: int
    spend_amount: float


class ThemeRow(BaseModel):
    theme: str
    cofog_code: Optional[str] = None
    decision_count: int  # talk
    spend_amount: float  # money (0.0 when none)
    spend_count: int
    talk_share: float  # % of total decision_count
    spend_share: float  # % of total spend_amount
    monthly: List[MonthlyPoint] = []


class Totals(BaseModel):
    decision_count: int
    spend_amount: float
    spend_count: int


class MoneyAndTalkResponse(BaseModel):
    as_of: str  # "YYYY-MM-DD"
    note: str
    totals: Totals
    themes: List[ThemeRow] = []


# Theme-level rollup across the filtered rows. NUMERIC -> float for the wire.
_THEMES_SQL = """
    SELECT canonical_theme,
           cofog_code,
           COALESCE(SUM(decision_count), 0)::bigint   AS decision_count,
           COALESCE(SUM(spend_amount), 0)::float8      AS spend_amount,
           COALESCE(SUM(spend_count), 0)::bigint       AS spend_count
    FROM topic_money_and_talk
    WHERE ($1::text IS NULL OR jurisdiction_id = $1)
      AND ($2::text IS NULL OR state_code = $2)
      AND canonical_theme IS NOT NULL
    GROUP BY canonical_theme, cofog_code
    ORDER BY spend_amount DESC, decision_count DESC
"""

# Per-theme monthly series (same filter). cofog_code is included so a theme that
# spans multiple COFOG codes keys to the right rollup row. Ascending by month.
_MONTHLY_SQL = """
    SELECT canonical_theme,
           cofog_code,
           to_char(month, 'YYYY-MM')                   AS month,
           COALESCE(SUM(decision_count), 0)::bigint    AS decision_count,
           COALESCE(SUM(spend_amount), 0)::float8       AS spend_amount
    FROM topic_money_and_talk
    WHERE ($1::text IS NULL OR jurisdiction_id = $1)
      AND ($2::text IS NULL OR state_code = $2)
      AND canonical_theme IS NOT NULL
      AND month IS NOT NULL
    GROUP BY canonical_theme, cofog_code, month
    ORDER BY canonical_theme, cofog_code, month ASC
"""


def _share(part: float, whole: float) -> float:
    """Percent of whole, rounded to 1 dp; 0.0 when the denominator is 0."""
    if not whole:
        return 0.0
    return round(part / whole * 100, 1)


@router.get("", response_model=MoneyAndTalkResponse)
async def get_money_and_talk(
    jurisdiction_id: Optional[str] = Query(None, description="Exact jurisdiction_id filter."),
    state_code: Optional[str] = Query(None, description="2-letter or full state name filter."),
) -> MoneyAndTalkResponse:
    """Theme-level money-vs-talk rollup with a sparse per-theme monthly series.

    Default (no filter) is national. An empty result set returns zeroed totals
    and no themes — the frontend renders an explicit empty state.
    """
    norm_state = normalize_state_input(state_code) if state_code else None
    as_of = date.today().isoformat()

    with tracer.start_as_current_span("money-and-talk") as span:
        span.set_attribute("money_and_talk.jurisdiction_id", jurisdiction_id or "")
        span.set_attribute("money_and_talk.state_code", norm_state or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("money-and-talk-themes"):
                    theme_rows = await conn.fetch(_THEMES_SQL, jurisdiction_id, norm_state)
                with tracer.start_as_current_span("money-and-talk-monthly"):
                    month_rows = await conn.fetch(_MONTHLY_SQL, jurisdiction_id, norm_state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("money-and-talk query failed")
            span.record_exception(exc)
            return MoneyAndTalkResponse(
                as_of=as_of,
                note=_NOTE,
                totals=Totals(decision_count=0, spend_amount=0.0, spend_count=0),
                themes=[],
            )

        # Bucket the monthly series by (theme, cofog_code) so it attaches to the
        # matching rollup row. None cofog normalises to "" for keying.
        monthly_by_key: dict[tuple[str, str], List[MonthlyPoint]] = {}
        for m in month_rows:
            key = (m["canonical_theme"], m["cofog_code"] or "")
            monthly_by_key.setdefault(key, []).append(
                MonthlyPoint(
                    month=m["month"],
                    decision_count=int(m["decision_count"]),
                    spend_amount=float(m["spend_amount"]),
                )
            )

        total_decisions = sum(int(r["decision_count"]) for r in theme_rows)
        total_spend = sum(float(r["spend_amount"]) for r in theme_rows)
        total_spend_count = sum(int(r["spend_count"]) for r in theme_rows)

        themes: List[ThemeRow] = []
        for r in theme_rows:
            dc = int(r["decision_count"])
            sa = float(r["spend_amount"])
            key = (r["canonical_theme"], r["cofog_code"] or "")
            themes.append(
                ThemeRow(
                    theme=r["canonical_theme"],
                    cofog_code=r["cofog_code"],
                    decision_count=dc,
                    spend_amount=sa,
                    spend_count=int(r["spend_count"]),
                    talk_share=_share(dc, total_decisions),
                    spend_share=_share(sa, total_spend),
                    monthly=monthly_by_key.get(key, []),
                )
            )

        span.set_attribute("money_and_talk.theme_count", len(themes))
        return MoneyAndTalkResponse(
            as_of=as_of,
            note=_NOTE,
            totals=Totals(
                decision_count=total_decisions,
                spend_amount=total_spend,
                spend_count=total_spend_count,
            ),
            themes=themes,
        )
