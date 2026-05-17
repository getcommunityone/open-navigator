"""
Hackathon demo scope: limit states/jurisdictions and LLM caps for Colab runs.

Set ``SCOPE`` in the notebook (``fast`` | ``medium`` | ``full``), default ``fast``.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from governance_meeting_llm import MeetingInventory

ENV_KEY = "GOVERNANCE_DEMO_SCOPE"


@dataclass(frozen=True)
class DemoScopePreset:
    key: str
    label: str
    eta: str
    max_states: int
    max_jurisdictions: int
    meeting_dates: int
    max_pdfs_per_jur: int
    max_pages_per_pdf: int
    max_audio_per_jur: int
    max_audio_chunks: int
    parallel_states: int
    max_images_per_jur: int


PRESETS: Dict[str, DemoScopePreset] = {
    "fast": DemoScopePreset(
        key="fast",
        label="Fast (1 state, 1 jurisdiction)",
        eta="~15–25 min",
        max_states=1,
        max_jurisdictions=1,
        meeting_dates=1,
        max_pdfs_per_jur=1,
        max_pages_per_pdf=4,
        max_audio_per_jur=1,
        max_audio_chunks=2,
        parallel_states=1,
        max_images_per_jur=0,
    ),
    "medium": DemoScopePreset(
        key="medium",
        label="Standard (2 states, 2 jurisdictions)",
        eta="~35–50 min",
        max_states=2,
        max_jurisdictions=2,
        meeting_dates=2,
        max_pdfs_per_jur=2,
        max_pages_per_pdf=6,
        max_audio_per_jur=1,
        max_audio_chunks=3,
        parallel_states=2,
        max_images_per_jur=6,
    ),
    "full": DemoScopePreset(
        key="full",
        label="Full (4 states, 4 jurisdictions)",
        eta="~90+ min",
        max_states=4,
        max_jurisdictions=4,
        meeting_dates=3,
        max_pdfs_per_jur=3,
        max_pages_per_pdf=8,
        max_audio_per_jur=1,
        max_audio_chunks=4,
        parallel_states=4,
        max_images_per_jur=12,
    ),
}


def normalize_scope_key(raw: str) -> str:
    key = (raw or "fast").strip().lower()
    aliases = {
        "1": "fast",
        "one": "fast",
        "fastest": "fast",
        "2": "medium",
        "two": "medium",
        "standard": "medium",
        "4": "full",
        "slow": "full",
        "slowest": "full",
        "max": "full",
    }
    return aliases.get(key, key if key in PRESETS else "fast")


def get_active_preset() -> DemoScopePreset:
    return PRESETS[normalize_scope_key(os.environ.get(ENV_KEY, "fast"))]


def apply_preset_to_environ(preset: DemoScopePreset) -> None:
    """Push preset limits into os.environ for downstream cells."""
    os.environ[ENV_KEY] = preset.key
    os.environ["GOVERNANCE_MODE"] = "DEMO"
    os.environ["GOVERNANCE_DEMO_DATE_SCOPE"] = "1"
    os.environ["GOVERNANCE_DEMO_YEAR_SCOPE"] = "1"
    os.environ["GOVERNANCE_DEMO_MEETING_DATES"] = str(preset.meeting_dates)
    os.environ["GOVERNANCE_DEMO_MAX_PDFS_PER_JUR"] = str(preset.max_pdfs_per_jur)
    os.environ["GOVERNANCE_DEMO_MAX_PAGES_PER_PDF"] = str(preset.max_pages_per_pdf)
    os.environ["GOVERNANCE_DEMO_MAX_AUDIO_PER_JUR"] = str(preset.max_audio_per_jur)
    os.environ["GOVERNANCE_DEMO_MAX_AUDIO_CHUNKS"] = str(preset.max_audio_chunks)
    os.environ["GOVERNANCE_DEMO_MAX_IMAGES_PER_JUR"] = str(preset.max_images_per_jur)
    os.environ["GOVERNANCE_PARALLEL_STATES"] = str(preset.parallel_states)
    # Gatekeeper: filename/manifest rules (no PDF/API); match hackathon scope.
    os.environ["GOVERNANCE_GATEKEEPER_RULES_ONLY"] = "1"
    os.environ["GOVERNANCE_GATEKEEPER_MAX_MEETING_SESSIONS"] = str(preset.meeting_dates)
    if not os.environ.get("GOVERNANCE_GATEKEEPER_MAX_FILES", "").strip():
        os.environ["GOVERNANCE_GATEKEEPER_MAX_FILES"] = str(
            max(
                6,
                (preset.max_pdfs_per_jur + preset.max_audio_per_jur) * preset.meeting_dates,
            )
        )


def apply_scope(scope: str) -> DemoScopePreset:
    """Validate ``scope``, set env caps, return preset."""
    key = normalize_scope_key(scope)
    preset = PRESETS[key]
    apply_preset_to_environ(preset)
    return preset


def filter_inventories_for_scope(
    inventories: List[MeetingInventory],
    preset: DemoScopePreset,
) -> List[MeetingInventory]:
    """One jurisdiction per state (richest media first), up to preset limits."""
    by_state: Dict[str, List[MeetingInventory]] = defaultdict(list)
    for inv in inventories:
        by_state[inv.jurisdiction.state_code].append(inv)

    selected: List[MeetingInventory] = []
    for state in sorted(by_state.keys()):
        if len(selected) >= preset.max_jurisdictions:
            break
        states_so_far = {inv.jurisdiction.state_code for inv in selected}
        if state not in states_so_far and len(states_so_far) >= preset.max_states:
            continue
        invs = sorted(
            by_state[state],
            key=lambda i: (
                -(len(i.pdfs) + len(i.audio)),
                i.jurisdiction.relative_label,
            ),
        )
        if invs:
            selected.append(invs[0])
    return selected[: preset.max_jurisdictions]


def print_scope_plan(
    preset: DemoScopePreset,
    all_inventories: List[MeetingInventory],
    selected: List[MeetingInventory],
) -> None:
    print(f"\n{'=' * 60}")
    print(f"SCOPE = {preset.key!r}  →  {preset.label}  ({preset.eta})")
    print(f"{'=' * 60}")
    print(
        f"  Caps: {preset.max_states} state(s), {preset.max_jurisdictions} jurisdiction(s), "
        f"{preset.meeting_dates} meeting date(s), "
        f"{preset.max_pdfs_per_jur} PDF(s)/jur, {preset.max_audio_chunks} audio chunk(s)"
    )
    print(f"  On disk: {len(all_inventories)} jurisdiction(s) with media")
    print(f"  This run: {len(selected)} jurisdiction(s)")
    for inv in selected:
        j = inv.jurisdiction
        print(f"    • {j.relative_label}  (pdfs={len(inv.pdfs)} audio={len(inv.audio)})")
    if len(all_inventories) > len(selected):
        print(
            f"  Skipped: {len(all_inventories) - len(selected)} "
            f"(raise SCOPE to medium or full in §2)"
        )
    print(f"{'=' * 60}\n")
