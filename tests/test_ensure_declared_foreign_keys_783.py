"""#783: ensure_declared_foreign_keys restores declared FKs that a CASCADE drop removed.

Renders the dbt macro with plain Jinja against a fake graph and a fake database, so
the logic (what it adds, what it skips, that it never deletes) is checked without
dbt or Postgres.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[1]
MACRO = ROOT / "dbt_project" / "macros" / "ensure_declared_foreign_keys.sql"


class _Result:
    def __init__(self, rows):
        self.rows = rows


class _Db:
    """Answers the macro's catalog queries from flags; records every statement."""

    def __init__(self, *, tables_exist=True, fk_present=False, parent_unique=True, orphans=0):
        self.tables_exist = tables_exist
        self.fk_present = fk_present
        self.parent_unique = parent_unique
        self.orphans = orphans
        self.statements: list[str] = []

    def run_query(self, sql: str):
        self.statements.append(sql)
        s = " ".join(sql.split())
        if "to_regclass" in s:
            return _Result([[self.tables_exist]])
        if "c.contype = 'f'" in s:
            return _Result([[1]] if self.fk_present else [])
        if "ix.indisunique" in s:
            return _Result([[1]] if self.parent_unique else [])
        if s.startswith("select count(*)"):
            return _Result([[self.orphans]])
        return _Result([])

    @property
    def alters(self) -> list[str]:
        return [s for s in self.statements if s.strip().lower().startswith("alter table")]


def _node(name, *, schema="gold", constraints=None, columns=None, materialized="table"):
    return {
        "resource_type": "model",
        "name": name,
        "alias": name,
        "schema": schema,
        "config": {"materialized": materialized},
        "constraints": constraints or [],
        "columns": columns or {},
    }


def _render(db: _Db, *, dry_run=False, to='"postgres"."gold"."jurisdictions"'):
    child = _node(
        "bills",
        constraints=[
            {
                "type": "foreign_key",
                "columns": ["jurisdiction_id"],
                "to": to,
                "to_columns": ["jurisdiction_id"],
            }
        ],
    )
    parent = _node("jurisdictions")
    logs: list[str] = []
    env = jinja2.Environment(extensions=["jinja2.ext.do"])
    src = MACRO.read_text(encoding="utf-8")
    ctx = {
        "execute": True,
        "target": SimpleNamespace(type="postgres"),
        "graph": SimpleNamespace(nodes={"model.p.bills": child, "model.p.jurisdictions": parent}),
        "run_query": db.run_query,
        "adapter": SimpleNamespace(quote=lambda c: f'"{c}"'),
        "modules": SimpleNamespace(re=re),
        "log": lambda msg, info=False: logs.append(msg) or "",
        "return": lambda v: v,
    }
    template = env.from_string(src + "{{ ensure_declared_foreign_keys(dry_run) }}")
    template.render(dry_run=dry_run, **ctx)
    return logs


@pytest.mark.parametrize("to", ['"postgres"."gold"."jurisdictions"', "ref('jurisdictions')", 'gold.jurisdictions'])
def test_macro_reads_the_parent_from_every_form_of_to(to):
    """dbt hands the graph a rendered relation, not ref(...): found with a real dbt run (#783)."""
    db = _Db()
    _render(db, to=to)
    assert len(db.alters) == 1 and "references gold.jurisdictions" in db.alters[0]


def test_macro_adds_missing_foreign_key():
    db = _Db()
    logs = _render(db)
    assert len(db.alters) == 1
    alter = db.alters[0]
    assert "gold.bills" in alter and "references gold.jurisdictions" in alter
    assert "foreign key (jurisdiction_id)" in alter
    assert any("1 added" in line for line in logs)


def test_macro_skips_and_names_a_child_with_orphans():
    db = _Db(orphans=12)
    logs = _render(db)
    assert db.alters == []
    assert any("12 orphan row(s); not added" in line for line in logs)


def test_macro_never_deletes_anything():
    db = _Db(orphans=5)
    _render(db)
    assert not any(re.search(r"\b(delete|truncate|drop)\b", s, re.I) for s in db.statements)


def test_macro_leaves_an_existing_key_alone_whatever_its_name():
    db = _Db(fk_present=True)
    logs = _render(db)
    assert db.alters == []
    assert any("1 already present" in line for line in logs)


def test_macro_skips_when_parent_has_no_unique_key():
    db = _Db(parent_unique=False)
    logs = _render(db)
    assert db.alters == []
    assert any("has no unique key" in line for line in logs)


def test_macro_skips_when_tables_not_built():
    db = _Db(tables_exist=False)
    logs = _render(db)
    assert db.alters == []
    assert any("not built yet" in line for line in logs)


def test_dry_run_reports_but_does_not_alter():
    db = _Db()
    logs = _render(db, dry_run=True)
    assert db.alters == []
    assert any("(dry run): 1 added" in line for line in logs)


def test_macro_is_wired_into_on_run_end():
    cfg = (ROOT / "dbt_project" / "dbt_project.yml").read_text(encoding="utf-8")
    assert "ensure_declared_foreign_keys()" in cfg


def test_ballot_measures_primary_key_is_declared():
    pk = (ROOT / "dbt_project" / "macros" / "ensure_gold_primary_keys.sql").read_text(encoding="utf-8")
    assert "'table': 'ballot_measures'" in pk
