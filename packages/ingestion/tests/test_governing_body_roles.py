"""Body member roles and roster name keys (#1443): the Python twin of the dbt macros, on real roster titles/names."""

from __future__ import annotations

import pytest

from ingestion.governance.roles import load_role_rules, name_key, role_of

RULES = load_role_rules()


@pytest.mark.parametrize(
    "title, role",
    [
        # Titles as person_government / person_government_term / Legistar give them.
        ("Mayor", "mayor"),
        ("City Councilor", "council_member"),
        ("City Councilor (Mayor Pro Tempore)", "president_pro_tem"),
        ("President Pro Tempore", "president_pro_tem"),
        ("City Council President", "president"),
        ("Vice Mayor", "vice_mayor"),
        ("Alderman", "alderman"),
        ("Council Member", "council_member"),
        ("Vice Chair", "vice_chair"),
        ("Chair", "chair"),
        ("Commissioner", "commissioner"),
        ("Supervisor", "supervisor"),
        ("City Clerk", "clerk"),
        ("Ranking Democratic Member", "member"),
        ("Member", "member"),
        ("", "member"),
        (None, "member"),
    ],
)
def test_role_of(title: str, role: str) -> None:
    assert role_of(title, RULES) == role


@pytest.mark.parametrize(
    "name, key",
    [
        ("Joseph Eatmon, Sr.", "joseph eatmon"),
        ("Woodrow Washington III", "woodrow washington"),
        ("Julia M. Mejia", "julia mejia"),
        ("Walt Maddox", "walt maddox"),
        ("Dr. Jane O'Neil", "jane oneil"),
        ("Cher", None),
    ],
)
def test_name_key(name: str, key: str) -> None:
    assert name_key(name) == key


def test_roster_match_is_exact_not_fuzzy() -> None:
    # Same person written two ways matches; a different first name does not.
    assert name_key("Lee Busby") == name_key("Lee R. Busby")
    assert name_key("Lee Busby") != name_key("Leo Busby")
