"""Totals from the usage logs (#262).

    python -m llm.usage.report                      # every day in the log directory
    python -m llm.usage.report --since 2026-11-01   # from a date
    python -m llm.usage.report --by stage           # group calls by stage as well
    python -m llm.usage.report --json               # the same rows as JSON

Model calls are grouped by day, model and API mode; GPU steps by day, step and
GPU. A cost appears only where ``prices.yaml`` has a sourced, dated price for
the model or GPU. Otherwise the column is blank: no cost is assumed.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from llm.usage.calls import TOKEN_COLUMNS, usage_log_dir
from llm.usage.load_bronze import read_rows
from llm.usage.prices import call_cost_usd, gpu_cost_usd, load_prices

CALL_COLUMNS = [
    "day", "model", "api_mode", "call_count", "failed_call_count", "retried_call_count",
    *TOKEN_COLUMNS, "avg_latency_seconds", "max_latency_seconds", "cost_usd",
]  # fmt: skip
GPU_COLUMNS = [
    "day", "step_name", "gpu_name", "run_count", "wall_seconds", "gpu_hours",
    "avg_gpu_utilization_pct", "max_gpu_memory_used_mb", "energy_wh", "estimated_cost_usd",
]  # fmt: skip


def _day(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "")[:10]


def _sum_cost(costs: list[float | None]) -> float | None:
    """The total, or ``None`` if any row has no cost: a partial sum would read as the whole."""
    if not costs or any(c is None for c in costs):
        return None
    return round(sum(costs), 4)


def summarize_calls(
    rows: Iterable[dict[str, Any]],
    prices: dict[str, Any],
    *,
    since: str = "",
    extra_keys: Sequence[str] = (),
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        day = _day(row, "called_at")
        if since and day < since:
            continue
        key = (day, row.get("model"), row.get("api_mode") or "interactive",
               *(row.get(k) for k in extra_keys))  # fmt: skip
        groups.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        members = groups[key]
        latencies = [r["latency_seconds"] for r in members if r.get("latency_seconds") is not None]
        summary: dict[str, Any] = {"day": key[0], "model": key[1], "api_mode": key[2]}
        summary.update(dict(zip(extra_keys, key[3:])))
        summary["call_count"] = len(members)
        summary["failed_call_count"] = sum(1 for r in members if not r.get("is_ok"))
        summary["retried_call_count"] = sum(1 for r in members if (r.get("attempt_count") or 1) > 1)
        for column in TOKEN_COLUMNS:
            values = [r[column] for r in members if r.get(column) is not None]
            summary[column] = sum(values) if values else None
        summary["avg_latency_seconds"] = (
            round(sum(latencies) / len(latencies), 2) if latencies else None
        )
        summary["max_latency_seconds"] = max(latencies) if latencies else None
        # Failed calls report no tokens and are not billed, so they are left out of the cost.
        summary["cost_usd"] = _sum_cost(
            [call_cost_usd(r, prices) for r in members if r.get("is_ok")]
        )
        out.append(summary)
    return out


def summarize_gpu(
    rows: Iterable[dict[str, Any]], prices: dict[str, Any], *, since: str = ""
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        day = _day(row, "started_at")
        if since and day < since:
            continue
        groups.setdefault((day, row.get("step_name"), row.get("gpu_name")), []).append(row)
    out: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        members = groups[key]
        wall = sum(r.get("wall_seconds") or 0 for r in members)
        utils = [
            (r["avg_gpu_utilization_pct"], r.get("wall_seconds") or 0)
            for r in members
            if r.get("avg_gpu_utilization_pct") is not None
        ]
        weight = sum(w for _, w in utils)
        peaks = [r["max_gpu_memory_used_mb"] for r in members if r.get("max_gpu_memory_used_mb") is not None]
        energy = [r["energy_wh"] for r in members if r.get("energy_wh") is not None]
        out.append(
            {
                "day": key[0],
                "step_name": key[1],
                "gpu_name": key[2],
                "run_count": len(members),
                "wall_seconds": round(wall, 1),
                "gpu_hours": round(sum(r.get("gpu_hours") or 0 for r in members), 4),
                # mean utilization over the steps, weighted by how long each ran
                "avg_gpu_utilization_pct": (
                    round(sum(u * w for u, w in utils) / weight, 2) if weight else None
                ),
                "max_gpu_memory_used_mb": max(peaks) if peaks else None,
                "energy_wh": round(sum(energy), 3) if energy else None,
                "estimated_cost_usd": _sum_cost([gpu_cost_usd(r, prices) for r in members]),
            }
        )
    return out


def format_table(rows: list[dict[str, Any]], columns: Sequence[str]) -> str:
    """A plain text table; a missing value prints as a dash."""
    if not rows:
        return "(no rows)"

    def cell(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    table = [list(columns)] + [[cell(r.get(c)) for c in columns] for r in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(columns))]
    lines = ["  ".join(v.ljust(w) for v, w in zip(line, widths)).rstrip() for line in table]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--log-dir", default=None, help="Usage log directory (default: LLM_USAGE_LOG_DIR)")
    parser.add_argument("--since", default="", help="First day to include, YYYY-MM-DD")
    parser.add_argument(
        "--by",
        action="append",
        default=[],
        choices=["stage", "jurisdiction_id", "run_id"],
        help="Also group model calls by this label (repeatable)",
    )
    parser.add_argument("--prices", default=None, help="Prices file (default: the package's prices.yaml)")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of tables")
    args = parser.parse_args()

    log_dir = Path(args.log_dir).expanduser() if args.log_dir else usage_log_dir()
    prices = load_prices(Path(args.prices) if args.prices else None)
    calls = summarize_calls(
        read_rows(log_dir, "llm_calls"), prices, since=args.since, extra_keys=args.by
    )
    gpu = summarize_gpu(read_rows(log_dir, "gpu_runs"), prices, since=args.since)
    if args.json:
        print(json.dumps({"llm_calls": calls, "gpu_runs": gpu}, indent=2))
        return
    call_columns = CALL_COLUMNS[:3] + list(args.by) + CALL_COLUMNS[3:]
    print(f"Model calls ({log_dir})")
    print(format_table(calls, call_columns))
    print()
    print("GPU steps")
    print(format_table(gpu, GPU_COLUMNS))
    if any(r["cost_usd"] is None for r in calls) or any(r["estimated_cost_usd"] is None for r in gpu):
        print()
        print("A dash under cost means prices.yaml has no sourced, dated price for that model or GPU.")


if __name__ == "__main__":
    main()
