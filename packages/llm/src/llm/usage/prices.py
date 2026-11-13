"""Prices for usage rows, and a row's cost at those prices (#262).

A cost is returned only when the price that applies has a value, a source and a
read date in ``prices.yaml``. Otherwise it is ``None`` and the report shows a
blank: a cost is never assumed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

PRICES_FILE = Path(__file__).with_name("prices.yaml")
_RATE_KEYS = ("input_usd_per_1m", "output_usd_per_1m")


def load_prices(path: Optional[Path] = None) -> Dict[str, Any]:
    import yaml

    data = yaml.safe_load(Path(path or PRICES_FILE).read_text(encoding="utf-8")) or {}
    return {"models": data.get("models") or {}, "gpus": data.get("gpus") or {}}


def _sourced(entry: Any) -> bool:
    return isinstance(entry, dict) and bool(entry.get("source")) and bool(entry.get("read_date"))


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def model_price(model: str, api_mode: str, prices: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The rates for ``model`` in ``api_mode``: the exact id, else the longest
    listed id the model's name starts with (a dated or preview variant). ``None``
    unless the entry is sourced, dated and has both the input and output rate."""
    models = prices.get("models") or {}
    name = (model or "").strip()
    key = name if name in models else max(
        (k for k in models if name.startswith(k)), key=len, default=None
    )
    entry = models.get(key) if key else None
    if not _sourced(entry):
        return None
    rates = entry.get(api_mode or "interactive")
    if not isinstance(rates, dict) or not all(_positive(rates.get(k)) for k in _RATE_KEYS):
        return None
    return {**rates, "source": entry["source"], "read_date": str(entry["read_date"])}


def call_cost_usd(row: Dict[str, Any], prices: Dict[str, Any]) -> Optional[float]:
    """One call's cost: uncached input at the input rate, cached input at the
    cached rate, output plus thinking at the output rate. ``None`` when a price or
    a token count needed for it is missing."""
    rates = model_price(row.get("model") or "", row.get("api_mode") or "interactive", prices)
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


def gpu_price(gpu_name: str, prices: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The sourced, dated price whose key appears in the GPU's name (longest key wins)."""
    name = (gpu_name or "").upper()
    gpus = prices.get("gpus") or {}
    key = max((k for k in gpus if k.upper() in name), key=len, default=None)
    entry = gpus.get(key) if key else None
    if not _sourced(entry) or not _positive(entry.get("usd_per_gpu_hour")):
        return None
    return entry


def gpu_cost_usd(row: Dict[str, Any], prices: Dict[str, Any]) -> Optional[float]:
    """One GPU step's estimated cost: its GPU-hours at the GPU's price, or ``None``."""
    entry = gpu_price(row.get("gpu_name") or "", prices)
    hours = row.get("gpu_hours")
    if entry is None or hours is None:
        return None
    return round(hours * entry["usd_per_gpu_hour"], 6)
