"""Operator-facing Discover issue rollup (#710).

Per-row ``Discover reject …`` lines are easy to miss in a long launch log.
This module accumulates accept/reject reasons and writes:

* ``data/cache/batch_jobs/ACTION_REQUIRED.md`` — stable path to open after a run
* ``data/cache/batch_jobs/discover_action_required_<stamp>.md`` — run copy
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

STABLE_ACTION_REQUIRED = Path("data/cache/batch_jobs/ACTION_REQUIRED.md")


def classify_reject_reason(reason: str) -> tuple[str, bool]:
    """Return (bucket_label, needs_operator_action)."""
    r = (reason or "").strip()
    low = r.lower()
    if "quotaexceeded" in low or "youtube.quota" in low:
        return (
            "uploads_fetch_failed:quotaExceeded (YouTube Data API daily quota)",
            True,
        )
    if "uploads_fetch_failed" in low and ("403" in low or "forbidden" in low):
        return (
            "uploads_fetch_failed:HTTP 403 (likely YouTube Data API quota)",
            True,
        )
    if "missing_youtube_api_key" in low:
        return ("missing_youtube_api_key", True)
    if r.startswith("channel_gate:"):
        return (r.split(":", 1)[0] + ":*", False)
    if r.startswith("jev_exhausted"):
        return ("jev_exhausted (no upload met keep threshold)", False)
    if r.startswith("uploads_fetch_failed"):
        return (r.split(":", 1)[0] + ":*", True)
    return (r[:160] or "unknown", False)


def format_uploads_fetch_failure(exc: BaseException) -> str:
    """Normalize uploads/playlist API errors so quota shows up in the reason string."""
    import urllib.error

    body = ""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        msg = f"HTTP Error {exc.code}: {exc.reason}"
    else:
        msg = str(exc)
    blob = f"{msg}\n{body}".lower()
    if "quotaexceeded" in blob or "youtube.quota" in blob:
        return "uploads_fetch_failed:quotaExceeded"
    if "403" in msg or "forbidden" in blob:
        return f"uploads_fetch_failed:HTTP Error 403: Forbidden"
    return f"uploads_fetch_failed:{msg[:240]}"


@dataclass
class DiscoverIssueStats:
    """Running rollup for one Discover CLI invocation."""

    states: list[str] = field(default_factory=list)
    accepts: list[str] = field(default_factory=list)
    reject_counts: Counter[str] = field(default_factory=Counter)
    reject_examples: dict[str, list[str]] = field(default_factory=dict)
    action_counts: Counter[str] = field(default_factory=Counter)
    noise_counts: Counter[str] = field(default_factory=Counter)
    source_log: str = ""
    _quota_warned: bool = False

    def note_state(self, state_code: str) -> None:
        sc = (state_code or "").strip().upper()
        if sc and sc not in self.states:
            self.states.append(sc)

    def record_accept(self, jurisdiction_id: Any, reason: str) -> None:
        jid = str(jurisdiction_id or "?").strip() or "?"
        self.accepts.append(f"{jid} — {reason}")

    def record_reject(self, jurisdiction_id: Any, reason: str) -> None:
        jid = str(jurisdiction_id or "?").strip() or "?"
        raw = str(reason or "unknown")
        bucket, actionable = classify_reject_reason(raw)
        self.reject_counts[bucket] += 1
        examples = self.reject_examples.setdefault(bucket, [])
        if jid not in examples and len(examples) < 12:
            examples.append(jid)
        if actionable:
            self.action_counts[bucket] += 1
            if "quota" in bucket.lower() and not self._quota_warned:
                self._quota_warned = True
                logger.error(
                    "Discover ACTION REQUIRED: YouTube Data API quota exhausted "
                    "(uploads/playlistItems 403). Channel hits will not bronze "
                    "until quota resets or YOUTUBE_API_KEY is replaced. "
                    "See {}",
                    STABLE_ACTION_REQUIRED,
                )
        else:
            self.noise_counts[bucket] += 1

    def write(
        self,
        *,
        out_dir: Path | None = None,
        stamp: str | None = None,
    ) -> Path:
        """Write stable + stamped markdown; return the stable path."""
        root = out_dir or STABLE_ACTION_REQUIRED.parent
        root.mkdir(parents=True, exist_ok=True)
        when = stamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        body = self.render_markdown(generated_at=datetime.now(timezone.utc))
        stable = root / "ACTION_REQUIRED.md"
        stamped = root / f"discover_action_required_{when}.md"
        stable.write_text(body, encoding="utf-8")
        stamped.write_text(body, encoding="utf-8")
        if self.action_counts:
            logger.error(
                "Discover finished with action-required issues — open {}",
                stable,
            )
        else:
            logger.info("Discover action summary (no operator blockers): {}", stable)
        return stable

    def render_markdown(self, *, generated_at: Optional[datetime] = None) -> str:
        when = (generated_at or datetime.now(timezone.utc)).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines: list[str] = [
            "# Discover — action required",
            "",
            f"_Generated {when}_",
            "",
            "## Status",
            "",
            f"- States: {', '.join(self.states) or '—'}",
            f"- Bronze accepts: **{len(self.accepts)}**",
            f"- Gated rejects: **{sum(self.reject_counts.values())}**",
        ]
        if self.source_log:
            lines.append(f"- Source log hint: `{self.source_log}`")
        lines.append("")

        lines.append("## Action required (you)")
        lines.append("")
        if not self.action_counts:
            lines.append("_None this run._")
            lines.append("")
        else:
            for bucket, n in self.action_counts.most_common():
                lines.append(f"### {bucket} ({n})")
                lines.append("")
                lines.extend(_action_guidance(bucket))
                ex = self.reject_examples.get(bucket) or []
                if ex:
                    lines.append(f"- Examples: {', '.join(f'`{x}`' for x in ex[:8])}")
                lines.append("")

        lines.append("## Reject rollup")
        lines.append("")
        lines.append("| Count | Reason | Examples |")
        lines.append("|------:|--------|----------|")
        for bucket, n in self.reject_counts.most_common():
            ex = ", ".join(self.reject_examples.get(bucket, [])[:5])
            lines.append(f"| {n} | `{bucket}` | {ex} |")
        if not self.reject_counts:
            lines.append("| 0 | — | — |")
        lines.append("")

        lines.append("## Accepts")
        lines.append("")
        if self.accepts:
            for a in self.accepts:
                lines.append(f"- `{a}`")
        else:
            lines.append("- _(none)_")
        lines.append("")

        lines.append("## Not action (noise)")
        lines.append("")
        if self.noise_counts:
            for bucket, n in self.noise_counts.most_common():
                lines.append(f"- {n}× `{bucket}`")
        else:
            lines.append("- _(none)_")
        lines.append("")
        return "\n".join(lines)


def _action_guidance(bucket: str) -> list[str]:
    low = bucket.lower()
    if "quota" in low or "403" in low:
        return [
            "- **What:** YouTube Data API daily quota is exhausted; Discover can "
            "still find channel URLs, but the uploads→Jev bronze gate cannot run.",
            "- **Do:**",
            "  1. Check [YouTube Data API quotas](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas) "
            "for the project that owns `YOUTUBE_API_KEY`.",
            "  2. Wait for the daily reset (~midnight Pacific), **or** put a key "
            "with remaining quota in `.env` as `YOUTUBE_API_KEY`, **or** request a quota increase.",
            "  3. Re-run Discover for states that rejected with this reason "
            "(accepted bronze rows are fine).",
        ]
    if "missing_youtube_api_key" in low:
        return [
            "- **What:** `YOUTUBE_API_KEY` is unset; bronze Jev gate cannot fetch uploads.",
            "- **Do:** Set `YOUTUBE_API_KEY` in `.env` and re-run Discover.",
        ]
    return [
        "- **What:** Discover recorded an operator-class failure; see reject examples.",
        "- **Do:** Inspect the launch log and fix the underlying dependency, then re-run.",
    ]
