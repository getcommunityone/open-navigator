"""The stance-shape cue rules (seed comment_stance_shape_terms, #1383) on caption-style snippets.

The seed holds Postgres regexes; ``\\y`` (word boundary) is the only construct Python spells differently. The
decision order below mirrors dbt macro ``stance_shape_sql``; a dbt run checks the same rules on the warehouse.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

SEED = Path(__file__).resolve().parents[3] / "dbt_project" / "seeds" / "comment_stance_shape_terms.csv"


def _rules() -> dict[str, re.Pattern[str]]:
    with SEED.open(newline="") as f:
        return {r["cue_kind"]: re.compile("(" + r["pattern"].replace(r"\y", r"\b") + ")", re.I) for r in csv.DictReader(f)}


def classify(text: str, concerns: bool = False) -> tuple[str, str | None]:
    hit = {k: (m.group(1) if (m := rx.search(text)) else None) for k, rx in _rules().items()}
    sup, opp = hit["support"], hit["oppose"]
    if hit["for_concept_against_project"]:
        return "for_concept_against_project", hit["for_concept_against_project"]
    if hit["condition"] and (sup or opp):
        return "conditional", hit["condition"]
    if hit["open_terms"] and opp:
        return "against_concept_open_to_terms", hit["open_terms"]
    if sup and not opp:
        return "clear_for", sup
    if opp and not sup:
        return "clear_against", opp
    if not sup and not opp and concerns:
        return "concerns_only", None
    return "unclear", None


def test_for_the_idea_against_this_site() -> None:
    shape, cue = classify("look I support data centers in general but not at this site next to the school")
    assert shape == "for_concept_against_project"
    assert cue and cue.lower().startswith("support data centers")


def test_conditional_only_if() -> None:
    shape, cue = classify("I would support it only if they pay their share of the water and the power upgrades")
    assert shape == "conditional"
    assert cue and cue.lower().startswith("only if they pay their share")


def test_conditional_as_long_as() -> None:
    assert classify("we oppose this as long as the noise limits are not in writing")[0] == "conditional"


def test_against_but_open_to_terms() -> None:
    shape, cue = classify("I oppose this rezoning unless the company agrees to a closed loop cooling system")
    assert shape == "against_concept_open_to_terms"
    assert cue and cue.lower().startswith("unless the company agrees")


def test_clear_sides() -> None:
    assert classify("I am strongly opposed to this project and I ask you to vote no")[0] == "clear_against"
    assert classify("We fully support this project and ask the council to approve it")[0] == "clear_for"


def test_do_not_support_is_not_support() -> None:
    assert classify("I do not support this and I cannot see how the grid will cope")[0] == "clear_against"


def test_concerns_without_a_side() -> None:
    assert classify("my well went dry last summer and the noise from the cooling fans worries me", concerns=True)[0] == "concerns_only"


def test_both_sides_without_a_shape_is_unclear() -> None:
    assert classify("I support the council and I oppose the mayor on the budget")[0] == "unclear"


def test_no_cue_is_unclear() -> None:
    assert classify("the meeting starts at six")[0] == "unclear"


def test_not_here_alone_is_not_a_site_objection() -> None:
    # Real caption: the speaker is saying someone is absent, not objecting to the site.
    assert classify("I like to straighten out with her but obviously she's not here and I support the council")[0] != "for_concept_against_project"


def test_just_not_here_is_a_site_objection() -> None:
    shape, cue = classify("we support new housing in general but just not here next to the creek")
    assert shape == "for_concept_against_project"
    assert cue and "not here" in cue


def test_if_they_would_is_not_open_to_terms() -> None:
    assert classify("I oppose this and if they would uh like talk about it later")[0] == "clear_against"


def test_elsewhere_needs_a_but() -> None:
    assert classify("I support that assertion that work is happening elsewhere")[0] != "for_concept_against_project"
    assert classify("I support them building but just somewhere else")[0] == "for_concept_against_project"
