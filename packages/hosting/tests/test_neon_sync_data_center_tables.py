"""#387: the data center serving tables reach Neon; the admin-kept links never get overwritten."""

from __future__ import annotations

import re
from pathlib import Path

from hosting.neon.sync_public_to_neon import CIVIC_SERVING, RUNTIME_OWNED

DATA_CENTER_SERVING = {
    "job_claim",
    "data_center_site",
    "data_center_agenda_item",
    "area_concern",
    "data_center_meeting_mention",
    "decision_place_label",
    "decision_company_mention",
    "decision_nearby_data_center_site",
    # #531: companies and projects
    "mdm_organization_data_center",
    "data_center_project",
    "data_center_project_company",
    "data_center_project_jurisdiction",
    "data_center_project_figure",
    "data_center_project_mention",
    # #532: company-hosted community meetings
    "data_center_community_event",
    "data_center_community_event_source",
    "data_center_community_event_recording",
}


def test_data_center_marts_are_mirrored() -> None:
    assert DATA_CENTER_SERVING <= CIVIC_SERVING


def test_admin_kept_links_are_runtime_owned_not_copied() -> None:
    assert "job_application_link" in RUNTIME_OWNED
    assert "job_application_link" not in CIVIC_SERVING


def test_contact_submission_is_runtime_owned_not_copied() -> None:
    # contact-form senders' emails stay private (#448)
    assert "contact_submission" in RUNTIME_OWNED
    assert "contact_submission" not in CIVIC_SERVING


def test_makefile_pii_mirror_matches_runtime_owned() -> None:
    makefile = Path(__file__).resolve().parents[3] / "Makefile"
    line = re.search(r"^PII_EXCLUDE_TABLES \?= (.+)$", makefile.read_text(), re.M)
    assert line is not None
    assert set(line.group(1).split()) == set(RUNTIME_OWNED)


# --- size budget -------------------------------------------------------------

from hosting.neon.sync_public_to_neon import (  # noqa: E402
    DEFAULT_MAX_MB,
    NEON_HARD_CAP_MB,
    SizeProjection,
    budget_problem,
    estimate_copy_bytes,
)

MB = 1024 * 1024


def test_estimate_adds_row_overhead_and_page_fill() -> None:
    assert estimate_copy_bytes(0, 0) == 0
    assert estimate_copy_bytes(1000, 10) == int((1000 + 10 * 28) * 1.15)


def test_final_size_swaps_old_for_new() -> None:
    p = SizeProjection(target_now_bytes=300 * MB, replaced_bytes=100 * MB, incoming_bytes=150 * MB,
                       largest_replaced_bytes=40 * MB)
    assert p.final_bytes == 350 * MB and p.peak_bytes == 390 * MB
    assert budget_problem(p, DEFAULT_MAX_MB) is None


def test_over_budget_is_refused() -> None:
    p = SizeProjection(target_now_bytes=400 * MB, replaced_bytes=50 * MB, incoming_bytes=150 * MB,
                       largest_replaced_bytes=10 * MB)
    problem = budget_problem(p, DEFAULT_MAX_MB)
    assert problem and "500 MB is over the 480 MB budget" in problem


def test_peak_over_the_hard_cap_is_refused_even_under_budget() -> None:
    p = SizeProjection(target_now_bytes=470 * MB, replaced_bytes=60 * MB, incoming_bytes=60 * MB,
                       largest_replaced_bytes=60 * MB)
    problem = budget_problem(p, DEFAULT_MAX_MB)
    assert problem and f"{NEON_HARD_CAP_MB} MB cap" in problem
