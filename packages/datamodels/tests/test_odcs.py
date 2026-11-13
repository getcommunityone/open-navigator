"""Open Data Contracts for the tables the public API serves (#270).

`python -m models.odcs --write` generates dbt_project/contracts/<model>.odcs.yaml from dbt's
own schema.yml files, for every relation publish_public_serving puts in `public` whose
schema.yml enforces a dbt contract. `python -m models.odcs --check` (run in CI) fails when a
contract is stale, missing, extra or not valid ODCS v3.1.0.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from models import odcs

REPO_ROOT = Path(__file__).resolve().parents[3]
DBT = REPO_ROOT / "dbt_project"

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

    # declared twice (model-level constraint and a relationships test): listed once
    assert props["grantor_master_org_id"]["relationships"] == [
        {"type": "foreignKey", "to": "mdm_organization.master_org_id"}
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
    assert contract["schema"][0]["relationships"] == [
        {
            "type": "foreignKey",
            "from": ["child.a", "child.b"],
            "to": ["parent.x", "parent.y"],
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
            "to": "parent.id",
            "customProperties": [{"property": "dbtTestSeverity", "value": "warn"}],
        }
    ]


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
    contracts, _ = odcs.build_contracts(DBT)
    assert len(contracts) >= 40
    for name, contract in contracts.items():
        assert odcs.validate(contract) == [], name
    broken = dict(next(iter(contracts.values())), apiVersion="v9.9.9")
    assert odcs.validate(broken)


def test_committed_contracts_are_current():
    assert odcs.check(DBT) == 0


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
    _, left_out = odcs.build_contracts(DBT)
    page = (
        REPO_ROOT / "web_docs" / "docs" / "development" / "data-contracts.md"
    ).read_text()
    for name in left_out:
        assert f"`{name}`" in page, (
            f"{name} is served without a contract but not listed in the page"
        )
