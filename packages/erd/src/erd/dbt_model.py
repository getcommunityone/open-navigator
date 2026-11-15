"""Read dbt `schema.yml` files into a model `erd.dictionary` can draw: each model's columns (name, data_type,
description), its primary key and foreign keys (dbt constraints, model- or column-level), and the relationships those
foreign keys make between the models read. Subject areas come from SUBJECT_AREAS (the first rule whose prefix matches a
model's name), packed into page columns by height. Kinds follow this repo's naming (no fact/dim names, CLAUDE.md):
a model another model points at is an "entity", a count, summary or aggregate is a "summary", the rest "event"."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import yaml

# (subject area, name prefixes): the first area whose prefix starts a model's name holds it; the rest go to "Other"
SUBJECT_AREAS: list[tuple[str, tuple[str, ...]]] = [
    ("Jurisdictions", ("jurisdiction", "dim_jurisdictions", "organizations_gov", "state_sales_tax", "cpi_")),
    ("Events and meetings", ("event", "meeting_", "decision_")),
    ("Bills and policy", ("bill", "rpt_bill", "policy_", "question_", "canonical_argument", "instance_argument")),
    ("People and organizations (MDM)", ("mdm_", "pending_mdm", "person_", "legislator", "contact_")),
    ("Elections", ("dim_candidate", "dim_election", "fct_")),
    ("Nonprofits and grants", ("grant", "nonprofit_", "organization_nonprofit")),
    ("Topics and tags", ("tag", "civicsearch_topic", "topic_", "item_")),
    ("Browse and reports", ("browse_", "opportunity_atlas")),
]
SUMMARY_WORDS = ("count", "summary", "aggregate", "trend", "lag", "annual", "rate", "revenue")
_REF = re.compile(r"""ref\(\s*['"]([^'"]+)['"]\s*\)""")


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str
    key: str = ""            # "PK", "FK" or "PK,FK"


@dataclass(frozen=True)
class Table:
    description: str
    columns: list = field(default_factory=list)


@dataclass(frozen=True)
class Relationship:
    parent: str
    child: str
    parent_cols: tuple
    child_cols: tuple
    label: str = ""
    cardinality: str = "||--o{"
    derived: bool = False


def _first_line(text: str | None) -> str:
    text = " ".join((text or "").split())
    return text[:160] + ("…" if len(text) > 160 else "")


def _target(to: str | None) -> str | None:
    m = _REF.search(to or "")
    return m.group(1) if m else None


def read_models(paths: list[Path]) -> dict[str, dict]:
    """{model name: its schema.yml entry} from every .yml under the given files or folders."""
    files = [f for p in paths for f in ([p] if p.is_file() else sorted(p.rglob("*.yml")))]
    models: dict[str, dict] = {}
    for f in files:
        for m in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("models", []) or []:
            if isinstance(m, dict) and m.get("name"):
                models[m["name"]] = m
    return models


def _keys(m: dict) -> tuple[set[str], list[tuple[str, tuple, tuple]]]:
    """(primary-key columns, [(target model, child cols, parent cols)]) from model- and column-level constraints."""
    pk: set[str] = set()
    fks: list[tuple[str, tuple, tuple]] = []
    for c in m.get("constraints", []) or []:
        if c.get("type") == "primary_key":
            pk |= set(c.get("columns", []) or [])
        elif c.get("type") == "foreign_key" and _target(c.get("to")):
            fks.append((_target(c["to"]), tuple(c.get("columns", []) or []), tuple(c.get("to_columns", []) or [])))
    for col in m.get("columns", []) or []:
        for c in col.get("constraints", []) or []:
            if c.get("type") == "primary_key":
                pk.add(col["name"])
            elif c.get("type") == "foreign_key" and _target(c.get("to")):
                fks.append((_target(c["to"]), (col["name"],), tuple(c.get("to_columns", []) or [col["name"]])))
    return pk, fks


def subject_area(name: str) -> str:
    return next((title for title, prefixes in SUBJECT_AREAS if name.startswith(prefixes)), "Other")


def build_model(models: dict[str, dict], page_columns: int = 4) -> SimpleNamespace:
    """The drawable model of the given dbt models; foreign keys to models not read are left out."""
    tables, relationships, parents = {}, [], set()
    for name, m in sorted(models.items()):
        pk, fks = _keys(m)
        fk_cols = {c for target, cols, _ in fks if target in models for c in cols}
        columns = []
        for col in m.get("columns", []) or []:
            key = ",".join(k for k, on in (("PK", col["name"] in pk), ("FK", col["name"] in fk_cols)) if on)
            columns.append(Column(col["name"], str(col.get("data_type") or ""), _first_line(col.get("description")), key))
        tables[name] = Table(_first_line(m.get("description")) or name, columns)
        for target, child_cols, parent_cols in fks:
            if target in models and target != name:
                relationships.append(Relationship(target, name, parent_cols, child_cols))
                parents.add(target)
    # keep only joins on declared columns, so every line has a row at both ends
    declared = {n: {c.name for c in t.columns} for n, t in tables.items()}
    relationships = [r for r in relationships
                     if set(r.child_cols) <= declared[r.child] and set(r.parent_cols) <= declared[r.parent]]
    kinds = {n: "entity" if n in parents else "summary" if any(w in n for w in SUMMARY_WORDS) else "event"
             for n in tables}
    by_area: dict[str, list[str]] = {}
    for n in tables:
        by_area.setdefault(subject_area(n), []).append(n)
    order = [t for t, _ in SUBJECT_AREAS if t in by_area] + (["Other"] if "Other" in by_area else [])
    # pack areas into page columns, the biggest first into the shortest column, then keep SUBJECT_AREAS order
    height = {a: sum(2 + len(tables[n].columns) for n in by_area[a]) / 2 for a in order}
    load, column_of = [0.0] * page_columns, {}
    for a in sorted(order, key=lambda a: -height[a]):
        c = load.index(min(load))
        column_of[a] = c
        load[c] += height[a]
    groups = [(a, column_of[a], by_area[a]) for a in order]
    return SimpleNamespace(TABLES=tables, RELATIONSHIPS=relationships, GROUPS=groups, KINDS=kinds,
                           PHI=set(), QUESTIONS={}, PROFILE=False)
