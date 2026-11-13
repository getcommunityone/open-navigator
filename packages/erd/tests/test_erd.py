"""erd: dbt schema.yml -> data-dictionary ERDs, a full view and an entity view in one arrangement."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from erd import build, build_model, read_models, write
from erd.dictionary import entity_columns

SCHEMA = """
version: 2
models:
  - name: jurisdictions
    description: One row per jurisdiction.
    columns:
      - name: jurisdiction_id
        data_type: text
        description: Primary key.
        constraints: [{type: not_null}, {type: primary_key}]
      - name: state_code
        data_type: text
        description: Two-letter state.
  - name: bills
    description: One row per bill.
    constraints:
      - type: foreign_key
        columns: [jurisdiction_id]
        to: ref('jurisdictions')
        to_columns: [jurisdiction_id]
    columns:
      - name: bill_uid
        data_type: text
        description: Primary key.
        constraints: [{type: primary_key}]
      - name: jurisdiction_id
        data_type: text
        description: The bill's jurisdiction.
      - name: title
        data_type: text
        description: The bill's title.
  - name: event_meeting
    description: One row per meeting.
    columns:
      - name: event_meeting_id
        data_type: text
        constraints: [{type: primary_key}]
      - name: jurisdiction_id
        data_type: text
        constraints:
          - type: foreign_key
            to: ref('jurisdictions')
            to_columns: [jurisdiction_id]
      - name: outside_id
        data_type: text
        constraints:
          - type: foreign_key
            to: ref('not_read_here')
            to_columns: [id]
  - name: browse_transcript_count
    description: One row per entity type.
    columns:
      - name: entity_type
        data_type: text
        constraints: [{type: primary_key}]
"""


@pytest.fixture()
def model(tmp_path: Path):
    (tmp_path / "_schema.yml").write_text(SCHEMA)
    return build_model(read_models([tmp_path]), page_columns=2)


def test_reads_keys_relationships_areas_and_kinds(model):
    assert set(model.TABLES) == {"jurisdictions", "bills", "event_meeting", "browse_transcript_count"}
    keys = {c.name: c.key for c in model.TABLES["bills"].columns}
    assert keys == {"bill_uid": "PK", "jurisdiction_id": "FK", "title": ""}
    meeting = {c.name: c.key for c in model.TABLES["event_meeting"].columns}
    assert meeting["jurisdiction_id"] == "FK" and meeting["outside_id"] == "", "a key to a model not read is left out"
    pairs = {(r.parent, r.child, r.child_cols) for r in model.RELATIONSHIPS}
    assert pairs == {("jurisdictions", "bills", ("jurisdiction_id",)),
                     ("jurisdictions", "event_meeting", ("jurisdiction_id",))}
    areas = {title: tables for title, _, tables in model.GROUPS}
    assert areas["Jurisdictions"] == ["jurisdictions"] and areas["Bills and policy"] == ["bills"]
    assert areas["Events and meetings"] == ["event_meeting"] and areas["Browse and reports"] == ["browse_transcript_count"]
    # this repo names tables by entity, never fact/dimension (CLAUDE.md)
    assert model.KINDS == {"jurisdictions": "entity", "bills": "event", "event_meeting": "event",
                           "browse_transcript_count": "summary"}


def test_the_entity_view_keeps_the_arrangement_and_drops_the_details(model):
    full, entity = build(model), build(model, entity=True)
    for title, _, tables in model.GROUPS:
        order = [sorted(tables, key=lambda t, d=d: (round(d.tables[t][1]), d.tables[t][0])) for d in (full, entity)]
        assert order[0] == order[1], title
    assert [a[0] < b[0] for a, b in pairwise(full.areas)] == [a[0] < b[0] for a, b in pairwise(entity.areas)]
    assert sum(w * h for *_, w, h in entity.areas) < sum(w * h for *_, w, h in full.areas)
    assert entity.columns["bills"] == [c.name for c in entity_columns(model, "bills")] == ["bill_uid", "jurisdiction_id"]
    xml = entity.xml("t")
    assert "EVENT table" in xml and "ENTITY table" in xml and "FACT" not in xml and "DIMENSION" not in xml
    assert "The bill's title" in full.xml("t") and "The bill's title" not in xml   # meanings only in the full view


def test_lines_are_right_angled_and_never_cross_a_table(model):
    for d in (build(model), build(model, entity=True)):
        assert len(d.routes) == len(model.RELATIONSHIPS)
        for route in d.routes:
            for (x1, y1), (x2, y2) in pairwise(route):
                assert x1 == x2 or y1 == y2
                lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
                for rx, ry, rw, rh in d.obstacles:
                    assert not (lo_x < rx + rw - 1 and hi_x > rx + 1 and lo_y < ry + rh - 1 and hi_y > ry + 1)


def test_write_gives_a_full_and_an_entity_file(model, tmp_path):
    paths = write("marts", model, None, tmp_path / "out")
    assert [p.name for p in paths] == ["marts_full.drawio", "marts_entity.drawio"]
    assert all("<mxfile" in p.read_text() and "Legend" in p.read_text() for p in paths)
