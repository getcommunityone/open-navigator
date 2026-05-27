#!/usr/bin/env python3
"""OpenStates people pipeline: load cloned people YAML into bronze.openstates_people.

Ported from load_openstates_people.py to the core_lib DataSourcePipeline
contract.

OpenStates maintains legislator data in a separate repository
(https://github.com/openstates/people). That repo is cloned/updated under
``data/cache/openstates_people/people`` and the per-person YAML files under
its ``data/<state>/{legislature,executive,municipalities}/*.yml`` directories
are imported into PostgreSQL.

Usage:
    python -m ingestion.openstates.people
    python -m ingestion.openstates.people --truncate
    python -m ingestion.openstates.people --no-clone --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:postgres@localhost:5433/openstates).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

try:  # PyYAML is required to parse the OpenStates people YAML files
    import yaml
except ImportError:  # pragma: no cover - surfaced clearly at runtime
    yaml = None  # type: ignore[assignment]


CACHE_DIR = Path("data/cache/openstates_people")
PEOPLE_REPO = "https://github.com/openstates/people.git"
BRONZE_TABLE = "bronze.openstates_people"


class DateEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date objects (preserved verbatim)."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def clone_or_update_repo(repo_path: Path) -> Path:
    """Clone the people repository or update it via ``git pull`` if it exists."""
    if repo_path.exists():
        subprocess.run(
            ["git", "pull"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
    else:
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", PEOPLE_REPO, str(repo_path)],
            check=True,
            capture_output=True,
        )
    return repo_path


def find_all_people_files(repo_path: Path) -> list[Path]:
    """Find all YAML files containing people data under the cloned repo."""
    data_dir = repo_path / "data"
    people_files: list[Path] = []
    for pattern in ["*/legislature/*.yml", "*/executive/*.yml", "*/municipalities/*.yml"]:
        people_files.extend(data_dir.glob(pattern))
    return people_files


def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    if yaml is None:  # pragma: no cover - import guard
        raise RuntimeError("PyYAML is required to parse OpenStates people files")
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def parse_person(person_data: dict[str, Any], state: str) -> dict[str, Any]:
    """Flatten an OpenStates person YAML document into row columns.

    Preserves the field-extraction logic from the legacy loader verbatim.
    """
    person_id = person_data.get("id")
    name = person_data.get("name")
    party = (
        person_data.get("party", [{}])[0].get("name")
        if person_data.get("party")
        else None
    )
    image = person_data.get("image")

    # Get current role
    roles = person_data.get("roles", [])
    current_role = roles[0] if roles else {}
    role_type = current_role.get("type")
    district = current_role.get("district")
    jurisdiction = current_role.get("jurisdiction")

    # Get contact info (Capitol Office)
    contact_details = person_data.get("contact_details", [])
    email = None
    phone = None
    address = None
    for contact in contact_details:
        if contact.get("note") == "Capitol Office":
            email = contact.get("email")
            phone = contact.get("voice")
            address = contact.get("address")

    return {
        "id": person_id,
        "name": name,
        "state": state.upper(),
        "party": party,
        "role_type": role_type,
        "district": district,
        "jurisdiction": jurisdiction,
        "email": email,
        "phone": phone,
        "address": address,
        "image": image,
        "data": person_data,
    }


class OpenstatesPeopleRow(RawRow):
    """One OpenStates person, validated before upsert into bronze.

    Constraints mirror the legacy ``openstates_people`` DDL: ``id`` is the
    primary key, ``name`` is NOT NULL, the rest are nullable. JSON column
    ``data`` is carried as a dict and JSON-cast at insert time.
    """

    id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=500)
    state: str | None = Field(default=None, max_length=2)
    party: str | None = Field(default=None, max_length=100)
    role_type: str | None = Field(default=None, max_length=50)
    district: str | None = Field(default=None, max_length=50)
    jurisdiction: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    image: str | None = Field(default=None, max_length=500)
    data: dict[str, Any] | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
        id              VARCHAR(255) PRIMARY KEY,
        name            VARCHAR(500) NOT NULL,
        state           VARCHAR(2),
        party           VARCHAR(100),
        role_type       VARCHAR(50),
        district        VARCHAR(50),
        jurisdiction    VARCHAR(100),
        email           VARCHAR(255),
        phone           VARCHAR(50),
        address         TEXT,
        image           VARCHAR(500),
        data            JSONB,
        created_at      TIMESTAMP DEFAULT NOW(),
        updated_at      TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(f"CREATE INDEX IF NOT EXISTS idx_people_state ON {BRONZE_TABLE}(state)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_people_party ON {BRONZE_TABLE}(party)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_people_role_type ON {BRONZE_TABLE}(role_type)"),
)

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {BRONZE_TABLE}")

_UPSERT_SQL = text(
    f"""
    INSERT INTO {BRONZE_TABLE} (
        id, name, state, party, role_type, district,
        jurisdiction, email, phone, address, image, data
    )
    VALUES (
        :id, :name, :state, :party, :role_type, :district,
        :jurisdiction, :email, :phone, :address, :image, CAST(:data AS jsonb)
    )
    ON CONFLICT (id) DO UPDATE SET
        name         = EXCLUDED.name,
        state        = EXCLUDED.state,
        party        = EXCLUDED.party,
        role_type    = EXCLUDED.role_type,
        district     = EXCLUDED.district,
        jurisdiction = EXCLUDED.jurisdiction,
        email        = EXCLUDED.email,
        phone        = EXCLUDED.phone,
        address      = EXCLUDED.address,
        image        = EXCLUDED.image,
        data         = EXCLUDED.data,
        updated_at   = NOW()
    """
)


class OpenstatesPeoplePipeline(DataSourcePipeline[OpenstatesPeopleRow]):
    source = "openstates_people"
    batch_size = 1_000
    row_schema = OpenstatesPeopleRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    def _repo_path(self) -> Path:
        return (self._path or CACHE_DIR) / "people"

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        repo_path = self._repo_path()
        if not repo_path.exists():
            raise FileNotFoundError(
                f"OpenStates people repo not found at {repo_path}. "
                f"Run with cloning enabled or clone {PEOPLE_REPO} first."
            )

        people_files = find_all_people_files(repo_path)
        emitted = 0
        for file_path in people_files:
            if self._limit is not None and emitted >= self._limit:
                return
            # State is the directory: data/<state>/legislature/file.yml
            state = file_path.parts[-3]
            person_data = load_yaml_file(file_path)
            if not isinstance(person_data, dict):
                continue
            cols = parse_person(person_data, state)
            if not cols.get("id") or not cols.get("name"):
                continue
            yield {
                "source": self.source,
                "source_version": repo_path.name,
                "natural_key": cols["id"],
                **cols,
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[OpenstatesPeopleRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "id": r.id,
                "name": r.name,
                "state": r.state,
                "party": r.party,
                "role_type": r.role_type,
                "district": r.district,
                "jurisdiction": r.jurisdiction,
                "email": r.email,
                "phone": r.phone,
                "address": r.address,
                "image": r.image,
                "data": json.dumps(r.data, cls=DateEncoder) if r.data is not None else None,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Load OpenStates people YAML into {BRONZE_TABLE}"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help=f"Directory holding the cloned people repo (default: {CACHE_DIR})",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Skip git clone/pull and use the already-cloned repo",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help=f"TRUNCATE {BRONZE_TABLE} before loading",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    cache_dir = args.cache_dir or CACHE_DIR
    if not args.no_clone:
        clone_or_update_repo(cache_dir / "people")
    await _prepare_target(args.truncate)
    pipeline = OpenstatesPeoplePipeline(path=cache_dir, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
