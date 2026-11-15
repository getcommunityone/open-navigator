"""ODPS data products for the public API's data contracts (#274).

`python -m models.odcs --write` also writes dbt_project/contracts/products/<product>.odps.yaml:
one ODPS v1.0.0 data product per `dataProduct` the ODCS contracts name, with one output port
per contract. `python -m models.odcs --check` also fails on a stale, missing or extra product
file, or one with a port whose contractId matches no contract.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from loguru import logger
from models import odcs, odps

REPO_ROOT = Path(__file__).resolve().parents[3]
DBT = REPO_ROOT / "dbt_project"
PRODUCT = "open-navigator-public-api"


def _model(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "config": {"contract": {"enforced": True}},
        "columns": [
            {
                "name": "id",
                "data_type": "text",
                "constraints": [{"type": "primary_key"}],
            }
        ],
    }


GRANT = _model("grant", "public.grant — one row per 990 grant line. PK grant_id.")
TAG = _model("tag", "Topic vocabulary, e.g. CAP codes. One row per node.")


def _contracts() -> dict:
    return {m["name"]: odcs.contract_for(m) for m in (GRANT, TAG)}


def test_one_product_per_data_product_with_a_port_per_contract():
    contracts = _contracts()
    products = odps.products_for(contracts)
    assert list(products) == [PRODUCT]
    product = products[PRODUCT]
    assert (product["apiVersion"], product["kind"], product["id"]) == (
        "v1.0.0",
        "DataProduct",
        PRODUCT,
    )
    assert (product["version"], product["status"]) == ("1.0.0", "active")
    assert product["name"] and product["domain"] and product["tags"]
    assert set(product["description"]) == {"purpose", "usage", "limitations"}
    assert "inputPorts" not in product  # the sources have no contracts

    ports = product["outputPorts"]
    assert [p["name"] for p in ports] == ["grant", "tag"]
    grant = ports[0]
    assert list(grant) == ["name", "version", "contractId", "type", "description"]
    assert (
        grant["contractId"] == contracts["grant"]["id"] == "open-navigator-public-grant"
    )
    assert grant["version"] == contracts["grant"]["version"]
    assert grant["type"] == "table"
    # one sentence, without the "public.<model> —" lead-in many dbt descriptions open with
    assert grant["description"] == "One row per 990 grant line."
    assert ports[1]["description"] == "Topic vocabulary, e.g. CAP codes."


def test_a_data_product_with_no_definition_fails():
    contracts = _contracts()
    contracts["tag"] = dict(contracts["tag"], dataProduct="somebody-elses-product")
    with pytest.raises(ValueError, match="somebody-elses-product"):
        odps.products_for(contracts)


def test_products_validate_against_the_official_schema():
    contracts = odcs.build_contracts(DBT).contracts
    products = odps.products_for(contracts)
    assert list(products) == [PRODUCT]
    product = products[PRODUCT]
    assert [p["contractId"] for p in product["outputPorts"]] == [
        c["id"] for c in contracts.values()
    ]
    assert odps.validate(product) == []
    assert odps.validate(dict(product, kind="DataContract"))
    assert odps.validate({k: v for k, v in product.items() if k != "status"})


def test_dangling_ports():
    product = odps.products_for(_contracts())[PRODUCT]
    ids = {"open-navigator-public-grant", "open-navigator-public-tag"}
    assert odps.dangling_ports(product, ids) == []
    assert odps.dangling_ports(product, ids - {"open-navigator-public-tag"}) == [
        "tag: contractId 'open-navigator-public-tag' matches no contract"
    ]


def test_committed_product_is_current():
    assert (DBT / "contracts" / "products" / f"{PRODUCT}.odps.yaml").is_file()
    assert odcs.check(DBT) == 0


def test_check_catches_stale_missing_extra_and_dangling_products(tmp_path):
    dbt = tmp_path / "dbt_project"
    (dbt / "macros").mkdir(parents=True)
    (dbt / "models").mkdir()
    (dbt / "macros" / "publish_public_serving.sql").write_text(
        "{%- set served = ['grant', 'tag'] -%}"
    )
    (dbt / "models" / "_schema.yml").write_text(
        yaml.safe_dump({"version": 2, "models": [GRANT, TAG]})
    )
    assert odcs.write(dbt) == 0
    path = dbt / "contracts" / "products" / f"{PRODUCT}.odps.yaml"
    assert path.is_file()
    assert odcs.check(dbt) == 0

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), format="{message}")
    try:
        # a port that names a contract that doesn't exist
        path.write_text(
            path.read_text().replace(
                "open-navigator-public-tag", "open-navigator-public-gone"
            )
        )
        assert odcs.check(dbt) == 1
        assert any("matches no contract" in m for m in messages)
        assert any("stale" in m for m in messages)
    finally:
        logger.remove(sink)
    odcs.write(dbt)
    assert odcs.check(dbt) == 0

    path.unlink()  # missing
    assert odcs.check(dbt) == 1
    odcs.write(dbt)
    shutil.copy(path, path.with_name(f"other{odps.SUFFIX}"))  # extra
    assert odcs.check(dbt) == 1
    odcs.write(dbt)  # regenerating removes the extra file
    assert odcs.check(dbt) == 0
