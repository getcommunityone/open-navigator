"""
"Follow the money" flow endpoint — GET /api/money-flow.

Returns Sankey-flow data for three lenses, ALL traced to the warehouse (no
fabricated numbers, per CLAUDE.md):
  - spending : real money-flagged decisions (public.item_interestingness,
               net_dollar_impact), jurisdiction -> decision.
  - grants   : real 990 Schedule I grant flows (public.grant), grantor -> grantee.
  - economy  : a real decomposition of nonprofit sector revenue into its 990
               components (contributions / program-service / other) — an honest
               breakdown of one real total, NOT invented funder->grantee edges.

WIRE-FORMAT: every displayed number is a STRING (head_amount / value_label). The
link `value` stays NUMERIC because the Sankey layout needs it to size links — it
is a chart magnitude, not a bare number rendered to the user.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/api/money-flow", tags=["money-flow"])
tracer = trace.get_tracer(__name__)

_ACCENT = {"spending": "#ea580c", "grants": "#0d9488", "economy": "#7c3aed"}


def money_fmt(value: Any) -> str:
    """Compact dollar string: $3.5B / $1.2M / $4.5K / $850. Plain string (wire rule)."""
    if value is None:
        return "$0"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "$0"
    sign = "-" if amount < 0 else ""
    mag = abs(amount)
    if mag >= 1_000_000_000_000:
        return f"{sign}${mag / 1_000_000_000_000:.1f}T"
    if mag >= 1_000_000_000:
        return f"{sign}${mag / 1_000_000_000:.1f}B"
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.1f}M"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}K"
    return f"{sign}${mag:.0f}"


def _trunc(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# Wire `window` string (shared with /api/lenses) -> interval days. 'auto'/'all'/
# unknown -> None (no date filter). Used to make the homepage WHEN selector
# actually scope the spending lens instead of being decorative.
_WINDOW_DAYS = {"month": 31, "quarter": 92, "year": 366, "fiveyear": 1830}


def _window_days(window: Optional[str]) -> Optional[int]:
    if not window:
        return None
    return _WINDOW_DAYS.get(window.strip().lower())


def _like(q: Optional[str]) -> Optional[str]:
    """A trimmed `%q%` ILIKE pattern, or None when there's no usable query."""
    q = (q or "").strip()
    return f"%{q}%" if q else None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class FlowMeta(BaseModel):
    title: str
    subtitle: Optional[str] = None
    url: Optional[str] = None
    source_label: Optional[str] = None


class FlowNode(BaseModel):
    name: str
    # Per-node drill-down target. Set on BOTH source and target nodes so either
    # side of the Sankey is clickable (a grantor node drills to that grantor's
    # grants just as a grantee node drills to the grantee's). None = not clickable.
    url: Optional[str] = None


class FlowLink(BaseModel):
    source: int
    target: int
    value: float  # numeric magnitude for the Sankey layout (not a user-facing bare number)
    value_label: str
    meta: FlowMeta


class FlowLens(BaseModel):
    accent: str
    head_amount: str = "—"
    head_label: str = ""
    # Aggregate drill-down for the headline figure (e.g. the full decisions /
    # grants / nonprofit list behind the summed total). None = not clickable.
    head_url: Optional[str] = None
    count_label: str = ""
    nodes: List[FlowNode] = []
    links: List[FlowLink] = []
    placeholder: bool = True


class MoneyFlowResponse(BaseModel):
    location_label: str
    lenses: Dict[str, FlowLens]


# ---------------------------------------------------------------------------
# Per-lens builders (each defensive: failure -> placeholder, never a 500)
# ---------------------------------------------------------------------------
# Decision-grain spending. The text filter ($3) and date window ($4) are NULL-able
# so the default homepage view (no query, 'auto'/'all' window) keeps the original
# "top 6 biggest decisions" behaviour; a search query or a WHEN selection narrows it.
_SPENDING_SQL = """
    SELECT event_decision_id, title, net_dollar_impact, outcome, occurred_at,
           votes_yes, votes_no, total_votes, jurisdiction_id
    FROM item_interestingness
    WHERE net_dollar_impact IS NOT NULL AND net_dollar_impact <> 0
      AND ($1::text IS NULL OR state_code = $1)
      AND ($2::text IS NULL OR jurisdiction_name ILIKE $2)
      AND ($3::text IS NULL OR title ILIKE $3)
      AND ($4::int  IS NULL OR (occurred_at IS NOT NULL
                                AND occurred_at >= (now() - make_interval(days => $4))))
    ORDER BY abs(net_dollar_impact) DESC
    LIMIT $5
"""

# Contract / financial-item grain — a DIFFERENT table & grain from the decisions
# above. Only searched when there is a query (many carry extraction-noise mega-
# amounts, so they must not pollute the default top-by-size view). amount > 0 drops
# zero-value "agreement" placeholders. item_date is the award/payment/effective date
# (NULL until the analysis prompt populates it) — the window filter is NULL-tolerant
# so undated contracts are never silently hidden.
_CONTRACTS_SQL = """
    SELECT event_financial_item_id, event_description, amount, amount_type,
           funding_source, item_date, item_date_type
    FROM event_financial_item
    WHERE amount IS NOT NULL AND amount > 0
      AND event_description ILIKE $1
      AND ($2::text IS NULL OR state_code = $2)
      AND ($3::text IS NULL OR jurisdiction_name ILIKE $3)
      AND ($4::int  IS NULL OR item_date IS NULL OR item_date >= (current_date - $4::int))
    ORDER BY amount DESC
    LIMIT 10
"""


async def _spending(
    conn,
    *,
    state_code: Optional[str],
    city: Optional[str],
    scope_label: str,
    q: Optional[str] = None,
    window: Optional[str] = None,
) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["spending"])
    q_like = _like(q)
    city_like = f"%{city}%" if city else None
    limit = 10 if q_like else 6
    days = _window_days(window)
    try:
        rows = await conn.fetch(_SPENDING_SQL, state_code, city_like, q_like, days, limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow spending failed: {}", exc)
        return lens

    # A uniform item shape so decisions and contracts can be ranked together by
    # dollar magnitude before the Sankey is built.
    items: List[Dict[str, Any]] = []
    juris_ids = {r["jurisdiction_id"] for r in rows if r["jurisdiction_id"]}
    for r in rows:
        sub_parts = []
        if r["outcome"]:
            sub_parts.append(r["outcome"])
        if r["occurred_at"]:
            sub_parts.append(r["occurred_at"].isoformat())
        if (r["total_votes"] or 0) > 0:
            sub_parts.append(f"{r['votes_yes']}–{r['votes_no']}")
        items.append({
            "amount": abs(float(r["net_dollar_impact"])),
            "title": r["title"] or "Untitled decision",
            "subtitle": " · ".join(sub_parts) or None,
            "url": f"/decisions/{r['event_decision_id']}",
            "source_label": "decision",
        })

    # Only fold in contracts/financial line-items when the user is searching, so a
    # specific item (e.g. a small water-plant contract) becomes reachable without
    # swamping the default view with noise-prone mega-amounts.
    if q_like:
        try:
            crows = await conn.fetch(_CONTRACTS_SQL, q_like, state_code, city_like, days)
        except Exception as exc:  # noqa: BLE001
            logger.warning("money-flow contracts failed: {}", exc)
            crows = []
        # Contracts have no reliable decision link, so they drill to the scoped
        # decisions map (honest broad target) rather than a fabricated decision page.
        c_url = f"/decisions-map?state={quote(state_code)}" if state_code else "/decisions-map"
        for r in crows:
            sub_bits = [(r["amount_type"] or "").strip()]
            if r["item_date"]:
                # e.g. "award 2026-02-14" — label by what the date represents when known.
                sub_bits.append(f"{(r['item_date_type'] or 'dated').strip()} {r['item_date'].isoformat()}")
            sub_bits.append((r["funding_source"] or "").strip())
            sub = " · ".join(p for p in sub_bits if p)
            items.append({
                "amount": abs(float(r["amount"])),
                "title": r["event_description"] or "Financial item",
                "subtitle": sub or None,
                "url": c_url,
                "source_label": r["amount_type"] or "contract",
            })

    if not items:
        return lens
    items.sort(key=lambda it: it["amount"], reverse=True)
    items = items[:limit]

    src = scope_label or "Local government"
    # Source node drill-down: when every (decision) spending row sits in a SINGLE
    # jurisdiction (a city-scoped view like "Tuscaloosa, AL"), drill into that
    # jurisdiction's own page rather than the broad geocoded decisions map.
    if len(juris_ids) == 1:
        src_url = f"/jurisdiction/{quote(str(next(iter(juris_ids))))}/meetings"
    elif state_code:
        src_url = f"/decisions-map?state={quote(state_code)}"
    else:
        src_url = "/decisions-map"
    nodes = [FlowNode(name=_trunc(src, 24), url=src_url)]
    links: List[FlowLink] = []
    total = 0.0
    n_contracts = 0
    for it in items:
        total += it["amount"]
        if it["source_label"] != "decision":
            n_contracts += 1
        nodes.append(FlowNode(name=_trunc(it["title"], 40), url=it["url"]))
        links.append(FlowLink(
            source=0, target=len(nodes) - 1, value=it["amount"], value_label=money_fmt(it["amount"]),
            meta=FlowMeta(
                title=it["title"], subtitle=it["subtitle"], url=it["url"],
                source_label=it["source_label"],
            ),
        ))
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    lens.head_label = "in tracked spending" + ("" if n_contracts else " decisions")
    lens.head_url = f"/decisions-map?state={quote(state_code)}" if state_code else "/decisions-map"
    n_dec = len(links) - n_contracts
    count = f"{n_dec} decisions" if n_dec else ""
    if n_contracts:
        count = f"{count} · {n_contracts} contracts" if count else f"{n_contracts} contracts"
    lens.count_label = count
    return lens


_GRANTS_SQL = """
    SELECT grant_id, grantor_name, grantee_name, amount, purpose, tax_year
    FROM "grant"
    WHERE amount IS NOT NULL AND amount > 0
      AND grantor_name IS NOT NULL AND grantee_name IS NOT NULL
      AND ($1::text IS NULL OR grantor_state_code = $1 OR grantee_state_code = $1)
      AND ($2::text IS NULL OR grantor_name ILIKE $2 OR grantee_name ILIKE $2
           OR purpose ILIKE $2)
    ORDER BY amount DESC
    LIMIT 6
"""


async def _grants(conn, *, state_code: Optional[str], q: Optional[str] = None) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["grants"])
    try:
        rows = await conn.fetch(_GRANTS_SQL, state_code, _like(q))
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow grants failed: {}", exc)
        return lens
    if not rows:
        return lens
    idx: Dict[str, int] = {}
    nodes: List[FlowNode] = []

    def node_for(name: str) -> int:
        key = name.strip()
        if key not in idx:
            idx[key] = len(nodes)
            # url is filled in after the loop — it points at this org's largest grant.
            nodes.append(FlowNode(name=_trunc(key, 28)))
        return idx[key]

    links: List[FlowLink] = []
    total = 0.0
    # Largest grant touching each node, so clicking an org label lands on that
    # org's most significant grant detail (there is no standalone org page).
    node_top: Dict[int, tuple] = {}
    for r in rows:
        s = node_for(r["grantor_name"])
        t = node_for(r["grantee_name"])
        amt = float(r["amount"])
        total += amt
        gid = r["grant_id"]
        sub = " · ".join(
            p for p in [(r["purpose"] or "").strip(), f"FY{r['tax_year']}" if r["tax_year"] else ""] if p
        )
        # Each flow IS one real grant row — drill straight to its grant detail
        # page (/grants/{id}), not a generic search.
        url = f"/grants/{gid}" if gid else "/search?types=grants"
        links.append(FlowLink(
            source=s, target=t, value=amt, value_label=money_fmt(amt),
            meta=FlowMeta(title=r["grantee_name"], subtitle=sub or None,
                          url=url, source_label="990 Schedule I"),
        ))
        for n in (s, t):
            if gid and (n not in node_top or amt > node_top[n][0]):
                node_top[n] = (amt, gid)
    # Point each org node at its biggest grant's detail page.
    for n, (_amt, gid) in node_top.items():
        nodes[n].url = f"/grants/{gid}"
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    lens.head_label = "in grant flows"
    # Drill down to the full grants list (990 Schedule I flows).
    lens.head_url = "/search?types=grants"
    lens.count_label = f"{len(links)} grants · 990 Schedule I"
    return lens


# Pre-aggregated nonprofit-sector revenue by scope, 1 row per scope_key — built by
# the `nonprofit_sector_revenue` mart so this lens is a PK lookup, NOT a 3.6M-row
# scan of mdm_organization_nonprofit (which has no geo of its own). The mart joins
# the satellite to its master org for state_code/city_norm. scope_key is one of
# 'us' | 'state:AL' | 'city:AL|tuscaloosa' (city_norm lowercased). We fetch the
# candidate keys most-specific-first and use the first non-empty grain (city ->
# state -> us), so a city with no 990 orgs still shows honest state/national
# context instead of an empty lens.
_ECONOMY_SQL = """
    SELECT scope_key, scope, state_code, city_norm,
           COALESCE(contributions, 0)           AS contributions,
           COALESCE(program_service_revenue, 0) AS program,
           COALESCE(total_revenue, 0)           AS total,
           COALESCE(org_count, 0)               AS orgs
    FROM nonprofit_sector_revenue
    WHERE scope_key = ANY($1::text[])
"""


def _economy_scope_keys(state_code: Optional[str], city: Optional[str]) -> List[str]:
    """Candidate scope_keys, most-specific first: city -> state -> us."""
    keys: List[str] = []
    if state_code and city:
        keys.append(f"city:{state_code}|{city.strip().lower()}")
    if state_code:
        keys.append(f"state:{state_code}")
    keys.append("us")
    return keys


async def _economy(conn, *, state_code: Optional[str], city: Optional[str], scope_label: str) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["economy"])
    candidates = _economy_scope_keys(state_code, city)
    try:
        rows = await conn.fetch(_ECONOMY_SQL, candidates)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow economy failed: {}", exc)
        return lens
    by_key = {r["scope_key"]: r for r in rows}
    # First candidate (most specific) with a real, non-zero total.
    row = next((by_key[k] for k in candidates if k in by_key and by_key[k]["total"]), None)
    if row is None:
        return lens
    total = float(row["total"])
    contrib = float(row["contributions"] or 0)
    program = float(row["program"] or 0)
    other = max(total - contrib - program, 0.0)
    nodes = [FlowNode(name="Nonprofit sector", url="/nonprofits")]
    links: List[FlowLink] = []
    for label, val in (("Contributions & grants", contrib), ("Program service revenue", program), ("Other revenue", other)):
        if val <= 0:
            continue
        nodes.append(FlowNode(name=label, url="/nonprofits"))
        pct = round(100.0 * val / total) if total else 0
        links.append(FlowLink(
            source=0, target=len(nodes) - 1, value=val, value_label=money_fmt(val),
            meta=FlowMeta(title=label, subtitle=f"~{pct}% of sector revenue",
                          url="/nonprofits", source_label="990 aggregate"),
        ))
    if not links:
        return lens
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    # Label by the grain that actually matched (which may differ from what was
    # requested if a city fell back to its state/national context), so the figure
    # never implies a scope it doesn't have.
    matched_scope = row["scope"]
    if matched_scope == "city":
        lens.head_label = f"{scope_label} nonprofit revenue"
        lens.count_label = f"{int(row['orgs']):,} orgs · 990"
    elif matched_scope == "state":
        lens.head_label = f"{row['state_code']} nonprofit revenue"
        lens.count_label = f"{int(row['orgs']):,} orgs · 990"
    else:  # 'us'
        lens.head_label = "U.S. nonprofit sector revenue"
        lens.count_label = f"{int(row['orgs']):,} orgs · 990 · nationwide"
    # Drill down to the nonprofit directory behind this aggregate.
    lens.head_url = "/nonprofits"
    return lens


@router.get("", response_model=MoneyFlowResponse)
async def get_money_flow(
    state: Optional[str] = Query(None, description="2-letter or full state name"),
    city: Optional[str] = Query(None, description="City name"),
    q: Optional[str] = Query(None, description="Free-text filter on spending/contract/grant descriptions"),
    window: Optional[str] = Query(None, description="Date window: month|quarter|year|fiveyear|all|auto"),
) -> MoneyFlowResponse:
    state_code = normalize_state_input(state)
    if state_code and city:
        scope_label = f"{city}, {state_code}"
    elif city:
        scope_label = city
    elif state_code:
        scope_label = state_code
    else:
        scope_label = "Local government"
    location_label = scope_label if (state_code or city) else "the U.S."

    with tracer.start_as_current_span("money-flow") as span:
        span.set_attribute("money_flow.state", state_code or "")
        span.set_attribute("money_flow.city", city or "")
        span.set_attribute("money_flow.q", (q or "").strip())
        span.set_attribute("money_flow.window", window or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            spending = await _spending(
                conn, state_code=state_code, city=city, scope_label=scope_label, q=q, window=window
            )
            grants = await _grants(conn, state_code=state_code, q=q)
            economy = await _economy(conn, state_code=state_code, city=city, scope_label=scope_label)

    return MoneyFlowResponse(
        location_label=location_label,
        lenses={"spending": spending, "grants": grants, "economy": economy},
    )
