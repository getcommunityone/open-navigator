"""
Hackathon demo scope: limit states/jurisdictions and LLM caps for Colab runs.

Set ``SCOPE`` in the notebook (``fast`` | ``medium`` | ``full``), default ``fast``.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .governance_meeting_llm import MeetingInventory, format_inventory_media_line

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
    preferred_jurisdiction_slug: Optional[str] = None
    pinned_meeting_date: Optional[str] = None  # YYYY-MM-DD — only this session
    default_media_scope: Optional[str] = None  # all | pdf | audio | video


PRESETS: Dict[str, DemoScopePreset] = {
    "fast": DemoScopePreset(
        key="fast",
        label="Tuscaloosa county — 2026-02-18 end-to-end (PDF + video)",
        eta="~45–75 min",
        max_states=1,
        max_jurisdictions=1,
        meeting_dates=1,
        max_pdfs_per_jur=6,
        max_pages_per_pdf=12,
        max_audio_per_jur=2,
        max_audio_chunks=4,
        parallel_states=1,
        max_images_per_jur=0,
        preferred_jurisdiction_slug="county_01125",
        pinned_meeting_date="2026-02-18",
        default_media_scope="all",
    ),
    "medium": DemoScopePreset(
        key="medium",
        label="Standard (2 states, 2 jurisdictions)",
        eta="~35–50 min",
        max_states=2,
        max_jurisdictions=2,
        meeting_dates=2,
        max_pdfs_per_jur=2,
        max_pages_per_pdf=12,
        max_audio_per_jur=2,
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
        max_pages_per_pdf=16,
        max_audio_per_jur=3,
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
        "county_e2e": "fast",
        "e2e": "fast",
        "2026_02_18": "fast",
        "tuscaloosa": "fast",
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
    os.environ.setdefault("GOVERNANCE_DEMO3_MAX_PDFS_PER_MEETING", "2")
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
    if preset.preferred_jurisdiction_slug:
        os.environ["GOVERNANCE_DEMO_JURISDICTION_SLUG"] = preset.preferred_jurisdiction_slug
    else:
        os.environ.pop("GOVERNANCE_DEMO_JURISDICTION_SLUG", None)
    if preset.pinned_meeting_date:
        os.environ["GOVERNANCE_DEMO_MEETING_DATE_PIN"] = preset.pinned_meeting_date
    else:
        os.environ.pop("GOVERNANCE_DEMO_MEETING_DATE_PIN", None)
    if preset.default_media_scope:
        try:
            from .pipeline_media_scope import apply_media_scope_to_environ

            apply_media_scope_to_environ(preset.default_media_scope)
        except ImportError:
            os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = preset.default_media_scope
    if not os.environ.get("GOVERNANCE_SAFETY_REVIEW", "").strip():
        os.environ["GOVERNANCE_SAFETY_REVIEW"] = "1"
    if preset.key == "fast":
        os.environ.setdefault("GOVERNANCE_DEMO3_INPUT", "auto")
        os.environ.setdefault("GOVERNANCE_DEMO_THINKING_BUDGET", "0")
        os.environ.setdefault("GOVERNANCE_THINKING_MODEL", "gemma-4-26b-a4b-it")
        os.environ.setdefault("GOVERNANCE_DEMO3_OCR_RESOLUTION", "LOW")
        os.environ.setdefault("GOVERNANCE_DEMO3_MAX_DOCUMENT_CHARS", "60000")
        os.environ.setdefault("GOVERNANCE_DEMO3_MIN_DIGITAL_CHARS", "200")
        os.environ.setdefault("GOVERNANCE_DEMO1_SKIP_WHEN_DIGITAL", "1")
        os.environ.setdefault("GOVERNANCE_DEMO2_SKIP_WHEN_DIGITAL", "1")


def apply_scope(scope: str) -> DemoScopePreset:
    """Validate ``scope``, set env caps, return preset."""
    key = normalize_scope_key(scope)
    preset = PRESETS[key]
    apply_preset_to_environ(preset)
    return preset


def resolve_media_scope_key(
    preset: DemoScopePreset,
    media_scope: Optional[str] = None,
) -> str:
    """
    Notebook §2 helper: ``media_scope=None`` uses the preset's ``default_media_scope`` (fast → ``all``).
    """
    if isinstance(media_scope, str) and media_scope.strip():
        return media_scope.strip()
    return (preset.default_media_scope or "all").strip()


def apply_scope_and_media(
    scope: str,
    media_scope: Optional[str] = None,
) -> Tuple[DemoScopePreset, str, Any]:
    """Apply demo scope + media scope; return ``(preset, media_key, media_config)``."""
    from .pipeline_media_scope import SCOPES as MEDIA_SCOPES, apply_media_scope, normalize_media_scope_key

    preset = apply_scope(scope)
    media = resolve_media_scope_key(preset, media_scope)
    media_key = normalize_media_scope_key(media)
    if media_key not in MEDIA_SCOPES:
        raise ValueError(
            f"MEDIA_SCOPE must be one of {list(MEDIA_SCOPES)} (or *_only) — got {media!r}"
        )
    active_media = apply_media_scope(media)
    return preset, media, active_media


def _preferred_jurisdiction_slug(preset: DemoScopePreset) -> Optional[str]:
    env = os.environ.get("GOVERNANCE_DEMO_JURISDICTION_SLUG", "").strip()
    if env:
        return env
    return preset.preferred_jurisdiction_slug


def _pick_jurisdiction_for_state(
    invs: List[MeetingInventory],
    preset: DemoScopePreset,
) -> Optional[MeetingInventory]:
    """Prefer ``preset.preferred_jurisdiction_slug`` when present on disk."""
    slug = _preferred_jurisdiction_slug(preset)
    if slug:
        for inv in invs:
            if inv.jurisdiction.slug == slug:
                return inv
        for inv in invs:
            if slug in inv.jurisdiction.relative_label:
                return inv
    try:
        from .pipeline_media_scope import get_active_media_scope, inventory_richness_for_scope

        scope_key = get_active_media_scope().key
        richness = lambda i: inventory_richness_for_scope(i, scope_key)
    except ImportError:
        richness = lambda i: (len(i.pdfs) + len(i.audio), 0, 0)  # noqa: E731
    ranked = sorted(
        invs,
        key=lambda i: (
            richness(i),
            i.jurisdiction.relative_label,
        ),
        reverse=True,
    )
    return ranked[0] if ranked else None


def filter_inventories_for_scope(
    inventories: List[MeetingInventory],
    preset: DemoScopePreset,
) -> List[MeetingInventory]:
    """One jurisdiction per state (preferred slug, else richest media), up to preset limits."""
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
        pick = _pick_jurisdiction_for_state(by_state[state], preset)
        if pick is not None:
            selected.append(pick)
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
        f"{preset.max_pdfs_per_jur} PDF(s)/jur, "
        f"{preset.max_audio_per_jur} recording(s)/jur, "
        f"{preset.max_audio_chunks} chunk(s) each"
    )
    if preset.pinned_meeting_date:
        print(f"  Pinned meeting date: {preset.pinned_meeting_date}")
    if preset.default_media_scope:
        print(f"  Default media scope: {preset.default_media_scope!r} (PDF + recordings)")
    print(f"  On disk: {len(all_inventories)} jurisdiction(s) with media")
    pref = _preferred_jurisdiction_slug(preset)
    if pref:
        print(f"  Preferred jurisdiction slug: {pref!r} (when present on disk)")
    try:
        from .pipeline_media_scope import get_active_media_scope

        mscope = get_active_media_scope()
        print(f"  Media scope: {mscope.key!r} — {mscope.label}")
    except ImportError:
        pass
    print(f"  This run: {len(selected)} jurisdiction(s)")
    for inv in selected:
        j = inv.jurisdiction
        print(f"    • {j.relative_label}  ({format_inventory_media_line(inv)})")
    if len(all_inventories) > len(selected):
        print(
            f"  Skipped: {len(all_inventories) - len(selected)} "
            f"(raise SCOPE to medium or full in §2)"
        )
    print(f"{'=' * 60}\n")
