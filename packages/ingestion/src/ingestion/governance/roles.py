"""Body member roles and roster name keys (#1443).

Python twin of the dbt macros ``body_role`` and ``person_name_key`` (``dbt_project/macros/body_membership.sql``)
and the ordered rule seed ``dbt_project/seeds/body_role_rule.csv``. dbt does the work (``body_membership``); this
mirror lets pytest pin the behaviour on real roster titles and names. Change both together.

- ``role_of(title)``: the first rule (by priority) whose pattern matches the lower-cased title, with every
  character outside ``[a-z0-9 -]`` turned into a space. "City Councilor (Mayor Pro Tempore)" -> president_pro_tem,
  "Council Member" -> council_member, "Mayor" -> mayor.
- ``name_key(name)``: "first last" for roster matching: lower-case, punctuation dropped, suffixes (jr, sr, ii, iii,
  iv), honorifics (dr, mr, mrs, ms, hon) and single letters (middle initials) removed. "Joseph Eatmon, Sr." ->
  "joseph eatmon"; "Julia M. Mejia" -> "julia mejia".

Two names match only within the same body's jurisdiction, and only when the key is equal: no fuzzy matching, so a
name heard in a meeting never becomes an official without an exact roster entry.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from ingestion.governance.body_titles import default_seed_path

_NAME_DROP = re.compile(r"(^| )(jr|sr|ii|iii|iv|dr|mr|mrs|ms|hon|honorable|rev)(?= |$)")


def load_role_rules(path: Optional[Path] = None) -> list[tuple[int, str, str]]:
    with open(path or default_seed_path("body_role_rule.csv"), newline="", encoding="utf-8") as fh:
        rules = [(int(r["priority"]), r["pattern"], r["role"]) for r in csv.DictReader(fh)]
    return sorted(rules)


def normalize_title(title: Optional[str]) -> str:
    t = re.sub(r"[^a-z0-9 -]+", " ", (title or "").lower())
    return re.sub(r" +", " ", t).strip()


def role_of(title: Optional[str], rules: Optional[list[tuple[int, str, str]]] = None) -> str:
    t = normalize_title(title)
    for _, pattern, role in rules or load_role_rules():
        if re.search(pattern, t):
            return role
    return "member"


def name_key(name: Optional[str]) -> Optional[str]:
    n = re.sub(r"[^a-z ]+", " ", (name or "").lower().replace("'", "").replace("’", ""))
    n = re.sub(r" +", " ", n).strip()
    n = re.sub(_NAME_DROP, " ", n)
    words = [w for w in n.split(" ") if len(w) > 1]
    if len(words) < 2:
        return None
    return f"{words[0]} {words[-1]}"
