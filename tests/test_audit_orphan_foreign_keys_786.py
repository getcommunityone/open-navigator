"""#786: audit_orphan_foreign_keys must stay read-only and be valid dbt Jinja."""

from __future__ import annotations

import re
from pathlib import Path

import jinja2

MACRO = Path(__file__).resolve().parents[1] / "dbt_project" / "macros" / "audit_orphan_foreign_keys.sql"


def _sql_text() -> str:
    # Drop Jinja comments ({#- ... -#}) so the prose can mention words like "never creates".
    return re.sub(r"\{#.*?#\}", "", MACRO.read_text(encoding="utf-8"), flags=re.S)


def test_macro_parses_as_dbt_jinja():
    jinja2.Environment(extensions=["jinja2.ext.do"]).parse(MACRO.read_text(encoding="utf-8"))


def test_macro_only_reads():
    text = _sql_text().lower()
    for word in ("alter table", "drop ", "delete from", "truncate", "insert into", "update ", "create table", "add constraint"):
        assert word not in text, f"audit macro must be read-only, found: {word!r}"
    assert "select" in text


def test_macro_does_not_run_in_on_run_end():
    cfg = (MACRO.parents[1] / "dbt_project.yml").read_text(encoding="utf-8")
    assert "audit_orphan_foreign_keys" not in cfg  # operator-run only; it can scan large tables
