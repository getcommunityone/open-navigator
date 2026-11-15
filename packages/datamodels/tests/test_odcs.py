"""Open Data Contracts for the tables the public API serves (#270).

`python -m models.odcs --write` generates dbt_project/contracts/<model>.odcs.yaml from dbt's
own schema.yml files, for every relation publish_public_serving puts in `public` whose
schema.yml enforces a dbt contract. `python -m models.odcs --check` (run in CI) fails when a
contract is stale, missing, extra or not valid ODCS v3.1.0. Foreign keys point into other
contracts with fully qualified references, and only at properties those contracts hold (#276).
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest
import yaml
from loguru import logger
from models import odcs

REPO_ROOT = Path(__file__).resolve().parents[3]
DBT = REPO_ROOT / "dbt_project"
SCHEMA_DIR = DBT / "contracts" / "_schema"
DOCS_PAGE = REPO_ROOT / "web_docs" / "docs" / "development" / "data-contracts.md"
# ODCS v3.1.0's fully qualified reference to a property: the target contract's file (left out
# within the same contract), then the path to the property by schema object id and property id.
FULLY_QUALIFIED = re.compile(
    r"(?:(?P<file>[A-Za-z0-9_]+\.odcs\.yaml)#/)?"
    r"schema/(?P<table>[A-Za-z0-9_-]+)/properties/(?P<column>[A-Za-z0-9_-]+)"
)

MACRO = """
{%- set served = [
    'grant', 'tag',
    'contact_official'
] -%}

{%- set projections = {
    'contact_official':
        'select id, full_name, null::text as email, '
        'null::text as phone from gold.contact_official'
} -%}
"""

GRANT_YML = """
version: 2
models:
  - name: grant
    description: >
      public.grant — one row per 990 Schedule I grant line (grantor -> grantee).
      PK grant_id.
    config:
      contract:
        enforced: true
    constraints:
      - type: foreign_key
        columns: [grantor_master_org_id]
        to: ref('mdm_organization')
        to_columns: [master_org_id]
    columns:
      - name: grant_id
        description: "Surrogate grant-line id."
        data_type: text
        constraints:
          - type: not_null
          - type: primary_key
        tests:
          - unique
          - not_null
      - name: grantor_master_org_id
        description: "Golden org id of the grantor."
        data_type: text
        constraints:
          - type: not_null
        tests:
          - relationships:
              to: ref('mdm_organization')
              field: master_org_id
      - name: grant_status
        description: "Status of the grant line."
        data_type: varchar(32)
        data_tests:
          - accepted_values:
              values: ['paid', 'pledged']
      - name: cash_amount
        description: "Cash amount in US dollars."
        data_type: numeric
        constraints:
          - type: check
            expression: "cash_amount >= 0"
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1000000000
      - name: tax_year
        description: "Tax year of the filing."
        data_type: integer
"""


def _model(text: str, name: str) -> dict:
    return next(m for m in yaml.safe_load(text)["models"] if m["name"] == name)


def _props(contract: dict) -> dict:
    return {p["name"]: p for p in contract["schema"][0]["properties"]}


def _references(path: Path) -> list[str]:
    """Every foreign key's `to` and `from` in a contract file."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for table in doc["schema"]:
        for rel in table.get("relationships") or []:
            for side in ("from", "to"):
                found += rel[side] if isinstance(rel[side], list) else [rel[side]]
        for prop in table["properties"]:
            found += [rel["to"] for rel in prop.get("relationships") or []]
    return found


def _resolve(path: Path, reference: str) -> dict:
    """The property a reference names, read from the contract file it points at: a file in the
    same folder, or this one when the reference has no file part."""
    found = FULLY_QUALIFIED.fullmatch(reference)
    assert found, f"{path.name}: {reference!r} is not a fully qualified reference"
    target = path.with_name(found["file"]) if found["file"] else path
    assert target.is_file(), f"{path.name}: {reference!r} points at no file"
    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    tables = [t for t in doc["schema"] if t.get("id") == found["table"]]
    assert len(tables) == 1, (
        f"{path.name}: {reference!r} names no table of {target.name}"
    )
    props = [p for p in tables[0]["properties"] if p.get("id") == found["column"]]
    assert len(props) == 1, (
        f"{path.name}: {reference!r} names no column of {target.name}"
    )
    return props[0]


def test_served_relations_come_from_the_macro():
    assert odcs.served_relations(MACRO) == ["grant", "tag", "contact_official"]


@pytest.mark.parametrize(
    ("data_type", "logical"),
    [
        ("text", "string"),
        ("varchar(300)", "string"),
        ("tsvector", "string"),
        ("bigint", "integer"),
        ("integer", "integer"),
        ("numeric(6, 1)", "number"),
        ("double precision", "number"),
        ("boolean", "boolean"),
        ("date", "date"),
        ("timestamp with time zone", "timestamp"),
        ("timestamptz", "timestamp"),
        ("time without time zone", "time"),
        ("jsonb", "object"),
        ("text[]", "array"),
    ],
)
def test_logical_types(data_type, logical):
    assert odcs.logical_type(data_type) == logical


def test_a_contract_carries_keys_relationships_and_quality():
    contract = odcs.contract_for(_model(GRANT_YML, "grant"))
    assert contract["apiVersion"] == "v3.1.0"
    assert contract["kind"] == "DataContract"
    assert contract["id"] == "open-navigator-public-grant"
    assert contract["status"] == "active"
    table = contract["schema"][0]
    assert table["physicalName"] == "public.grant"
    assert table["dataGranularityDescription"].startswith(
        "One row per 990 Schedule I grant line"
    )
    # ids are what fully qualified references point at: the table's name, each column's name
    assert table["id"] == "grant"
    assert [p["id"] for p in table["properties"]] == [
        p["name"] for p in table["properties"]
    ]
    props = _props(contract)

    key = props["grant_id"]
    assert (
        key["primaryKey"],
        key["primaryKeyPosition"],
        key["required"],
        key["unique"],
    ) == (True, 1, True, True)
    assert key["logicalType"] == "string" and key["physicalType"] == "text"
    rules = {(r["type"], r.get("metric")) for r in key["quality"]}
    assert {("library", "nullValues"), ("library", "duplicateValues")} <= rules
    assert {r["severity"] for r in key["quality"]} == {"error"}

    # declared twice (model-level constraint and a relationships test): listed once, as a
    # fully qualified reference into the parent's contract file
    assert props["grantor_master_org_id"]["relationships"] == [
        {
            "type": "foreignKey",
            "to": "mdm_organization.odcs.yaml#/schema/mdm_organization/properties/master_org_id",
        }
    ]
    assert props["grantor_master_org_id"]["required"] is True

    status_rule = props["grant_status"]["quality"][0]
    assert status_rule["metric"] == "invalidValues"
    assert status_rule["arguments"] == {"validValues": ["paid", "pledged"]}
    assert status_rule["mustBe"] == 0

    text_rules = [
        r["description"] for r in props["cash_amount"]["quality"] if r["type"] == "text"
    ]
    assert any("cash_amount >= 0" in d for d in text_rules)
    assert any("0" in d and "1000000000" in d for d in text_rules)

    plain = props["tax_year"]
    assert (
        "required" not in plain
        and "quality" not in plain
        and "relationships" not in plain
    )


def test_composite_keys():
    model = {
        "name": "child",
        "description": "One row per child pair.",
        "config": {"contract": {"enforced": True}},
        "constraints": [
            {"type": "primary_key", "columns": ["a", "b"]},
            {
                "type": "foreign_key",
                "columns": ["a", "b"],
                "to": "ref('parent')",
                "to_columns": ["x", "y"],
            },
        ],
        "columns": [
            {"name": "a", "data_type": "text", "description": "first"},
            {"name": "b", "data_type": "bigint", "description": "second"},
        ],
    }
    contract = odcs.contract_for(model)
    props = _props(contract)
    assert (props["a"]["primaryKeyPosition"], props["b"]["primaryKeyPosition"]) == (
        1,
        2,
    )
    # each key column is not null, but only the pair is unique
    for column in ("a", "b"):
        assert props[column]["required"] is True
        assert "unique" not in props[column]
    # `from` is in this contract, so it needs no file part; `to` names the parent's file
    assert contract["schema"][0]["relationships"] == [
        {
            "type": "foreignKey",
            "from": ["schema/child/properties/a", "schema/child/properties/b"],
            "to": [
                "parent.odcs.yaml#/schema/parent/properties/x",
                "parent.odcs.yaml#/schema/parent/properties/y",
            ],
        }
    ]


def test_redacted_columns_are_marked_and_unprojected_columns_dropped():
    model = {
        "name": "contact_official",
        "description": "One row per official.",
        "config": {"contract": {"enforced": True}},
        "columns": [
            {
                "name": "id",
                "data_type": "text",
                "description": "id",
                "constraints": [{"type": "primary_key"}],
            },
            {
                "name": "email",
                "data_type": "text",
                "description": "email",
                "tests": ["not_null"],
            },
            {"name": "full_name", "data_type": "text", "description": "name"},
            {"name": "phone", "data_type": "text", "description": "phone"},
            {"name": "internal_note", "data_type": "text", "description": "gold only"},
        ],
    }
    projection = odcs.projections(MACRO)["contact_official"]
    contract = odcs.contract_for(model, projection)
    props = _props(contract)
    assert list(props) == [
        "id",
        "full_name",
        "email",
        "phone",
    ]  # the projection's order, as the view has it
    email = props["email"]
    assert {"property": "redactedInPublic", "value": True} in email["customProperties"]
    assert "required" not in email and "quality" not in email
    assert "null" in email["description"].lower()


def test_severity_and_conditions_are_kept():
    model = {
        "name": "t",
        "description": "One row per thing.",
        "config": {"contract": {"enforced": True}},
        "columns": [
            {
                "name": "k",
                "data_type": "text",
                "constraints": [{"type": "primary_key"}],
            },
            {
                "name": "soft",
                "data_type": "text",
                "tests": [
                    {"not_null": {"config": {"severity": "warn"}}},
                    {"unique": {"config": {"severity": "warn"}}},
                ],
            },
            {
                "name": "partial",
                "data_type": "text",
                "tests": [{"not_null": {"config": {"where": "kind = 'a'"}}}],
            },
            {
                "name": "parent_id",
                "data_type": "text",
                "data_tests": [
                    {
                        "relationships": {
                            "arguments": {"to": "ref('parent')", "field": "id"},
                            "config": {"severity": "warn"},
                        }
                    }
                ],
            },
        ],
    }
    props = _props(odcs.contract_for(model))
    # Postgres enforces a primary key as unique and not null, tests or no tests
    assert (props["k"]["required"], props["k"]["unique"]) == (True, True)
    soft = props["soft"]  # a warn-level test reports, it doesn't guarantee
    assert "required" not in soft and "unique" not in soft
    assert {r["severity"] for r in soft["quality"]} == {"warning"}
    partial = props["partial"]  # a filtered test holds only where its filter does
    assert "required" not in partial
    assert (
        partial["quality"][0]["type"] == "text"
        and "kind = 'a'" in partial["quality"][0]["description"]
    )
    assert props["parent_id"]["relationships"] == [
        {
            "type": "foreignKey",
            "to": "parent.odcs.yaml#/schema/parent/properties/id",
            "customProperties": [{"property": "dbtTestSeverity", "value": "warn"}],
        }
    ]


def test_a_reference_within_the_same_contract_has_no_file_part():
    model = {
        "name": "tag",
        "description": "One row per node of the topic tree.",
        "config": {"contract": {"enforced": True}},
        "columns": [
            {
                "name": "tag_id",
                "data_type": "text",
                "constraints": [{"type": "primary_key"}],
            },
            {
                "name": "parent_tag_id",
                "data_type": "text",
                "tests": [{"relationships": {"to": "ref('tag')", "field": "tag_id"}}],
            },
        ],
    }
    assert _props(odcs.contract_for(model))["parent_tag_id"]["relationships"] == [
        {"type": "foreignKey", "to": "schema/tag/properties/tag_id"}
    ]


LINKED_MACRO = """
{%- set served = ['grant', 'mdm_organization', 'pair', 'event_decision'] -%}

{%- set projections = {
    'mdm_organization':
        'select master_org_id from gold.mdm_organization'
} -%}
"""

# grant points at: a contracted parent's column (kept, with its dbt detail), a column that
# parent's public projection leaves out, a served relation with no contract, a contracted
# composite key, and a composite key into a relation that isn't served.
LINKED_YML = """
version: 2
models:
  - name: grant
    description: One row per grant line.
    config:
      contract:
        enforced: true
    constraints:
      - type: foreign_key
        columns: [pair_a, pair_b]
        to: ref('pair')
        to_columns: [a, b]
      - type: foreign_key
        columns: [pair_a, pair_b]
        to: ref('not_served')
        to_columns: [x, y]
    columns:
      - name: grant_id
        data_type: text
        constraints:
          - type: primary_key
      - name: grantor_master_org_id
        data_type: text
        tests:
          - relationships:
              to: ref('mdm_organization')
              field: master_org_id
              config:
                severity: warn
      - name: grantee_ein
        data_type: text
        tests:
          - relationships:
              to: ref('mdm_organization')
              field: ein
      - name: event_decision_id
        data_type: text
        tests:
          - relationships:
              to: ref('event_decision')
              field: event_decision_id
      - name: pair_a
        data_type: text
      - name: pair_b
        data_type: text
  - name: mdm_organization
    description: One row per organization.
    config:
      contract:
        enforced: true
    columns:
      - name: master_org_id
        data_type: text
        constraints:
          - type: primary_key
      - name: ein
        data_type: text
  - name: pair
    description: One row per pair.
    config:
      contract:
        enforced: true
    constraints:
      - type: primary_key
        columns: [a, b]
    columns:
      - name: a
        data_type: text
      - name: b
        data_type: text
  - name: event_decision
    description: One row per decision, served without an enforced contract.
    columns:
      - name: event_decision_id
"""


def test_a_foreign_key_with_no_contract_to_point_into_is_left_out(tmp_path):
    dbt = tmp_path / "dbt_project"
    (dbt / "macros").mkdir(parents=True)
    (dbt / "models").mkdir()
    (dbt / "macros" / "publish_public_serving.sql").write_text(LINKED_MACRO)
    (dbt / "models" / "_schema.yml").write_text(LINKED_YML)

    built = odcs.build_contracts(dbt)
    assert built.left_out == ["event_decision"]
    assert list(built.contracts) == ["grant", "mdm_organization", "pair"]
    props = _props(built.contracts["grant"])
    # resolved: kept with dbt's detail as the relationship's customProperties
    assert props["grantor_master_org_id"]["relationships"] == [
        {
            "type": "foreignKey",
            "to": "mdm_organization.odcs.yaml#/schema/mdm_organization/properties/master_org_id",
            "customProperties": [{"property": "dbtTestSeverity", "value": "warn"}],
        }
    ]
    # left out: a column the parent's contract doesn't hold, and a parent with no contract
    assert "relationships" not in props["grantee_ein"]
    assert "relationships" not in props["event_decision_id"]
    assert built.contracts["grant"]["schema"][0]["relationships"] == [
        {
            "type": "foreignKey",
            "from": [
                "schema/grant/properties/pair_a",
                "schema/grant/properties/pair_b",
            ],
            "to": [
                "pair.odcs.yaml#/schema/pair/properties/a",
                "pair.odcs.yaml#/schema/pair/properties/b",
            ],
        }
    ]
    assert built.left_out_keys == [
        "grant.grantee_ein -> mdm_organization.ein",
        "grant.event_decision_id -> event_decision.event_decision_id",
        "grant.(pair_a, pair_b) -> not_served.(x, y)",
    ]

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), format="{message}")
    try:
        assert odcs.write(dbt) == 0
    finally:
        logger.remove(sink)
    assert any(
        "grant.event_decision_id -> event_decision.event_decision_id" in m
        for m in messages
    )
    # the written files resolve, the composite key's `from` and `to` too
    written = dbt / "contracts" / "grant.odcs.yaml"
    for reference in _references(written):
        assert _resolve(written, reference)["id"] == reference.rsplit("/", 1)[1]
    assert len(_references(written)) == 5


@pytest.mark.parametrize(
    ("description", "grain"),
    [
        (
            "Totals, one row per government, from the U.S. Census Bureau. More.",
            "One row per government, from the U.S. Census Bureau.",
        ),
        (
            "Trend (one row per question_id x quarter). PK enforced.",
            "One row per question_id x quarter.",
        ),
        ("Scores per item, keyed by item_id.", None),
    ],
)
def test_grain_sentence(description, grain):
    model = {
        "name": "t",
        "description": description,
        "columns": [{"name": "a", "data_type": "text"}],
    }
    assert (
        odcs.contract_for(model)["schema"][0].get("dataGranularityDescription") == grain
    )


def test_materialize_mode_differences_are_stated():
    macro = (
        MACRO
        + """
{%- set neon_bodies = {
    'grant':
        kept_org_cte ~ "
select g.* from gold.grant g
where exists (select 1 from kept_org_ids k where k.id = g.grantor_id)",
    'tag':
        "select tag_id, label from gold.tag where year >= 2023"
} -%}
"""
    )
    assert odcs.serving_bodies(macro) == {"grant": "rows", "tag": "columns"}
    assert odcs.serving_bodies(MACRO) == {}
    grant = _model(GRANT_YML, "grant")
    default = odcs.contract_for(grant)["description"]["limitations"]
    rows = odcs.contract_for(grant, slimmed="rows")["description"]["limitations"]
    columns = odcs.contract_for(grant, slimmed="columns")["description"]["limitations"]
    assert "materialize" not in default
    assert "materialize" in rows and "fewer rows" in rows and "drops" not in rows
    assert (
        "materialize" in columns and "drops or nulls some of these columns" in columns
    )


def test_contracts_validate_against_the_official_schema():
    contracts = odcs.build_contracts(DBT).contracts
    assert len(contracts) >= 40
    for name, contract in contracts.items():
        assert odcs.validate(contract) == [], name
    broken = dict(next(iter(contracts.values())), apiVersion="v9.9.9")
    assert odcs.validate(broken)


def test_committed_contracts_are_current():
    assert odcs.check(DBT) == 0


def test_every_foreign_key_resolves_to_a_property_in_a_committed_contract():
    paths = sorted((DBT / "contracts").glob(f"*{odcs.SUFFIX}"))
    references = []
    for path in paths:
        [table] = yaml.safe_load(path.read_text(encoding="utf-8"))["schema"]
        assert table["id"] == table["name"] == path.name[: -len(odcs.SUFFIX)]
        assert all(p["id"] == p["name"] for p in table["properties"]), path.name
        references += [(path, reference) for reference in _references(path)]
    for path, reference in references:
        assert _resolve(path, reference)["id"] == reference.rsplit("/", 1)[1]
    # a check that resolved nothing would prove nothing: the contracts do point at each other
    assert any(FULLY_QUALIFIED.fullmatch(r)["file"] for _, r in references)


def test_check_catches_stale_missing_and_extra_contracts(tmp_path):
    dbt = tmp_path / "dbt_project"
    (dbt / "macros").mkdir(parents=True)
    (dbt / "models" / "marts").mkdir(parents=True)
    (dbt / "macros" / "publish_public_serving.sql").write_text(
        "{%- set served = ['grant'] -%}"
    )
    schema_yml = dbt / "models" / "marts" / "_schema_grant.yml"
    schema_yml.write_text(GRANT_YML)
    assert odcs.write(dbt) == 0
    assert odcs.check(dbt) == 0

    schema_yml.write_text(
        GRANT_YML.replace("Surrogate grant-line id.", "A changed description.")
    )
    assert odcs.check(dbt) == 1
    odcs.write(dbt)
    assert odcs.check(dbt) == 0

    (dbt / "contracts" / "grant.odcs.yaml").unlink()
    assert odcs.check(dbt) == 1
    odcs.write(dbt)
    shutil.copy(
        dbt / "contracts" / "grant.odcs.yaml",
        dbt / "contracts" / "not_served.odcs.yaml",
    )
    assert odcs.check(dbt) == 1


def test_left_out_relations_are_documented():
    left_out = odcs.build_contracts(DBT).left_out
    page = DOCS_PAGE.read_text(encoding="utf-8")
    for name in left_out:
        assert f"`{name}`" in page, (
            f"{name} is served without a contract but not listed in the page"
        )


def test_left_out_foreign_keys_are_documented():
    lines = DOCS_PAGE.read_text(encoding="utf-8").splitlines()
    for key in odcs.build_contracts(DBT).left_out_keys:
        child, parent = key.split(" -> ")
        assert any(f"`{child}`" in line and f"`{parent}`" in line for line in lines), (
            f"{key} is left out of the contracts but not listed in the page"
        )


def test_the_notice_gives_each_vendored_schemas_release_tag_and_sha256():
    notice = (SCHEMA_DIR / "NOTICE").read_text(encoding="utf-8")
    stated = {}
    for block in re.split(r"(?m)^(?=\S+\.json is )", notice):
        if named := re.match(r"(\S+\.json) is ", block):
            source = re.search(r"(?m)^Source:\s+(\S+)$", block)
            digest = re.search(r"(?m)^SHA-256:\s+([0-9a-f]{64})$", block)
            assert source and digest, (
                f"NOTICE gives no Source or SHA-256 for {named[1]}"
            )
            stated[named[1]] = (source[1], digest[1])
    assert sorted(stated) == sorted(p.name for p in SCHEMA_DIR.glob("*.json"))
    for name, (source, digest) in stated.items():
        assert hashlib.sha256((SCHEMA_DIR / name).read_bytes()).hexdigest() == digest, (
            f"{name} is not the file the NOTICE describes"
        )
        # the release tag the file is named for, never a branch that moves
        tag = re.search(r"-(v\d+\.\d+\.\d+)\.json$", name)[1]
        assert re.fullmatch(
            rf"https://raw\.githubusercontent\.com/bitol-io/[a-z-]+/{re.escape(tag)}/schema/"
            rf"{re.escape(name)}",
            source,
        ), source
