"""Prices for usage rows, and a row's cost at those prices (#262).

A cost is returned only when the price that applies has a value, a source and a
read date in ``prices.yaml``. Otherwise it is ``None`` and the report shows a
blank: a cost is never assumed.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

PRICES_FILE = Path(__file__).with_name("prices.yaml")
_RATE_KEYS = ("input_usd_per_1m", "output_usd_per_1m")
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def load_prices(path: Path | None = None) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load(Path(path or PRICES_FILE).read_text(encoding="utf-8")) or {}
    return {"models": data.get("models") or {}, "gpus": data.get("gpus") or {}}


def _sourced(entry: Any) -> bool:
    return isinstance(entry, dict) and bool(entry.get("source")) and bool(entry.get("read_date"))


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _call_moment(on: Any) -> datetime | None:
    """``on`` (an ISO timestamp) in UTC, or ``None`` when it has no time of day or doesn't parse. A timestamp
    with no offset is read as UTC, the zone usage rows are written in."""
    text = str(on or "").strip()
    if len(text) <= 10:  # a bare date, "YYYY-MM-DD"
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)


def _in_peak(peak: dict[str, Any], moment: datetime) -> bool:
    """Whether ``moment`` (UTC) falls in a peak window: on one of ``peak["days"]`` (every day when absent), from
    a window's start up to, but not including, its end. A window is ``"HH:MM-HH:MM"`` and doesn't cross
    midnight."""
    days = {str(day).strip().lower()[:3] for day in peak.get("days") or _WEEKDAYS}
    if _WEEKDAYS[moment.weekday()] not in days:
        return False
    clock = moment.time()
    for window in peak.get("hours_utc") or []:
        start, end = (time.fromisoformat(part.strip()) for part in str(window).split("-", 1))
        if start <= clock < end:
            return True
    return False


def model_price(
    model: str, api_mode: str, prices: dict[str, Any], *, on: str | None = None
) -> dict[str, Any] | None:
    """The rates for ``model`` in ``api_mode``: the exact id, else the longest
    listed id the model's name starts with (a dated or preview variant). ``None``
    unless the entry is sourced, dated and has both the input and output rate.

    An entry may carry ``valid_until: "YYYY-MM-DD"`` (the last day the rates
    apply). For a call made after that day (``on``, an ISO date or timestamp) the
    result is ``None``: the report shows no cost rather than a stale one (#333).

    An entry priced by time of day (DeepSeek, #328) carries ``peak`` (its ``days``
    and UTC ``hours_utc`` windows), and the mode's rates carry ``off_peak``. The
    mode's own rates apply in a peak window and ``off_peak`` outside one. Without
    the call's time of day (``on`` missing or a bare date) the result is ``None``,
    because the rate can't be chosen."""
    models = prices.get("models") or {}
    name = (model or "").strip()
    key = name if name in models else max(
        (k for k in models if name.startswith(k)), key=len, default=None
    )
    entry = models.get(key) if key else None
    if not _sourced(entry):
        return None
    valid_until = str(entry.get("valid_until") or "").strip()
    if valid_until and on and str(on)[:10] > valid_until:
        return None
    rates = entry.get(api_mode or "interactive")
    if not isinstance(rates, dict):
        return None
    peak = entry.get("peak")
    if isinstance(peak, dict) and isinstance(rates.get("off_peak"), dict):
        moment = _call_moment(on)
        if moment is None:
            return None
        if not _in_peak(peak, moment):
            rates = rates["off_peak"]
    rates = {k: v for k, v in rates.items() if k != "off_peak"}
    if not all(_positive(rates.get(k)) for k in _RATE_KEYS):
        return None
    return {**rates, "source": entry["source"], "read_date": str(entry["read_date"])}


def call_cost_usd(row: dict[str, Any], prices: dict[str, Any]) -> float | None:
    """One call's cost: uncached input at the input rate, cached input at the
    cached rate, output plus thinking at the output rate. ``None`` when a price or
    a token count needed for it is missing."""
    rates = model_price(
        row.get("model") or "", row.get("api_mode") or "interactive", prices, on=row.get("called_at")
    )
    input_tokens, output_tokens = row.get("input_token_count"), row.get("output_token_count")
    if rates is None or input_tokens is None or output_tokens is None:
        return None
    cached = row.get("cached_input_token_count") or 0
    thinking = row.get("thinking_token_count") or 0
    if cached and not _positive(rates.get("cached_input_usd_per_1m")):
        return None
    cost = (
        max(input_tokens - cached, 0) * rates["input_usd_per_1m"]
        + cached * (rates.get("cached_input_usd_per_1m") or 0)
        + (output_tokens + thinking) * rates["output_usd_per_1m"]
    ) / 1_000_000
    return round(cost, 6)


def gpu_price(gpu_name: str, prices: dict[str, Any]) -> dict[str, Any] | None:
    """The sourced, dated price whose key appears in the GPU's name (longest key wins)."""
    name = (gpu_name or "").upper()
    gpus = prices.get("gpus") or {}
    key = max((k for k in gpus if k.upper() in name), key=len, default=None)
    entry = gpus.get(key) if key else None
    if not _sourced(entry) or not _positive(entry.get("usd_per_gpu_hour")):
        return None
    return entry


def gpu_cost_usd(row: dict[str, Any], prices: dict[str, Any]) -> float | None:
    """One GPU step's estimated cost: its GPU-hours at the GPU's price, or ``None``."""
    entry = gpu_price(row.get("gpu_name") or "", prices)
    hours = row.get("gpu_hours")
    if entry is None or hours is None:
        return None
    return round(hours * entry["usd_per_gpu_hour"], 6)
