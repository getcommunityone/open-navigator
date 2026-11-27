"""The per-comment keyword seeds (#1233) match what they should on realistic comment text.

dbt applies these patterns with Postgres regex (``\\y`` / ``\\m`` / ``\\M`` word boundaries) on
lower(comment_text) (concerns, entities) or lower(intro_text) (roles); place shapes are
case-sensitive. Python's ``re`` reads the same patterns once the boundaries are translated.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

SEEDS = Path(__file__).resolve().parents[1] / "dbt_project" / "seeds"


def _py(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern.replace(r"\y", r"\b").replace(r"\m", r"\b").replace(r"\M", r"\b"))


def _load(name: str, key: str) -> dict[str, re.Pattern[str]]:
    with (SEEDS / name).open() as f:
        return {row[key]: _py(row["pattern"]) for row in csv.DictReader(f)}


CONCERNS = _load("comment_concern_terms.csv", "concern_key")
ENTITIES = _load("comment_entity_terms.csv", "entity_key")
ROLES = _load("comment_role_terms.csv", "role_key")
PLACES = _load("comment_place_patterns.csv", "pattern_key")


def hits(patterns: dict[str, re.Pattern[str]], text: str) -> set[str]:
    return {k for k, p in patterns.items() if p.search(text)}


def test_concerns_multi_label() -> None:
    text = (
        "this data center will drain our aquifer and the noise from the generators never stops. "
        "they signed ndas and are rushing this through with tax abatements, and it only brings 30 jobs."
    ).lower()
    found = hits(CONCERNS, text)
    assert {"water_use", "quality_of_life", "lack_of_transparency", "rushed_review", "taxpayer_subsidies",
            "few_jobs"} <= found
    assert "farmland_wildlife_loss" not in found


def test_concerns_do_not_fire_on_ordinary_words() -> None:
    assert hits(CONCERNS, "well, i think we should move on. thank you very much.") == set()
    # "jobs" alone (a supporter's point) is not the few-jobs concern.
    assert "few_jobs" not in hits(CONCERNS, "this project brings good union jobs to joliet")


def test_companies_people_and_ai() -> None:
    text = "google and amazon web services, elon musk's grok, chatgpt and artificial intelligence".lower()
    found = hits(ENTITIES, text)
    assert {"google", "amazon", "elon_musk", "xai", "openai", "ai"} <= found
    assert "ai" not in hits(ENTITIES, "the air is clean and the rain falls on maine")
    assert "anthropic" not in hits(ENTITIES, "my neighbor claude smith agrees")


def test_roles_from_self_introduction() -> None:
    assert {"resident", "union_worker"} <= hits(ROLES, "my name is jay and i'm a lifelong resident and ibew local 176 member")
    assert "staff_or_applicant" in hits(ROLES, "my name is david silverman. i'm an attorney with the law firm, representing the applicant")
    assert "possible_minor" in hits(ROLES, "my name is sam and i'm 12 years old")
    assert "possible_minor" in hits(ROLES, "i'm a junior at central high school")
    assert "possible_minor" not in hits(ROLES, "i'm a culinary arts teacher at joliet central high school")


def test_place_shapes_are_public_places() -> None:
    text = "The site off Route 9 near Oak Hill Elementary in Greene County, the Pine Ridge site, District 3"
    names = {m.group(0) for p in PLACES.values() for m in p.finditer(text)}
    assert "Route 9" in names
    assert any(n.endswith("Oak Hill Elementary") for n in names)
    assert any(n.endswith("Greene County") for n in names)
    assert any("Pine Ridge site" in n for n in names)
    assert "District 3" in names


def test_review_cases_for_roles_minors_and_ai() -> None:
    # A resident opposing the applicant is still a public comment.
    assert "staff_or_applicant" not in hits(ROLES, "my name is ann lee, i'm here to oppose the applicant's request and their consultants")
    assert "staff_or_applicant" in hits(ROLES, "my name is joe haresco. i'm with the acoustical consulting group retained by hillwood")
    assert "possible_minor" in hits(ROLES, "my name is ava and i'm in the fifth grade")
    assert "possible_minor" in hits(ROLES, "hi my name is max i am a twelve year old")
    assert "possible_minor" in hits(ROLES, "my name is leo and i'm 12")
    assert "ai" not in hits(ENTITIES, "the plan a. i think is bad")
