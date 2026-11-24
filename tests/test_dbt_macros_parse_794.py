"""#794: every dbt macro file must compile as Jinja.

A Jinja comment inside an expression ({# ... #} in a list) broke `dbt` for the whole project
(#784 shipped one in ensure_gold_primary_keys.sql). dbt compiles every macro on every command,
so one bad file stops everything. Plain Jinja with the `do` extension catches this class.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest

MACROS = sorted((Path(__file__).resolve().parents[1] / "dbt_project" / "macros").rglob("*.sql"))


@pytest.mark.parametrize("path", MACROS, ids=lambda p: p.name)
def test_macro_file_parses(path):
    jinja2.Environment(extensions=["jinja2.ext.do"]).parse(path.read_text(encoding="utf-8"))


def test_macros_were_found():
    assert len(MACROS) > 10


def test_no_jinja_comment_inside_the_primary_key_list():
    text = (MACROS[0].parent / "ensure_gold_primary_keys.sql").read_text(encoding="utf-8")
    start, end = text.index("{% set specs = ["), text.index("] %}")
    assert "{#" not in text[start:end]
