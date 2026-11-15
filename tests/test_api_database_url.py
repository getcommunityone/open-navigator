"""The ORM engine names the psycopg2 driver explicitly (#282).

SQLAlchemy 2.1 made ``postgresql://`` mean psycopg 3, which isn't installed, so an
implicit driver stopped ``api.main`` importing and took the live API down.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from api.database import sqlalchemy_url

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("postgresql://u:p@host:5433/db?sslmode=require", "postgresql+psycopg2://u:p@host:5433/db?sslmode=require"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("sqlite:///./data/users.db", "sqlite:///./data/users.db"),
    ],
)
def test_sqlalchemy_url_names_psycopg2(given: str, expected: str) -> None:
    assert sqlalchemy_url(given) == expected


def test_api_imports_with_a_postgres_url() -> None:
    """The failure on the Space: importing the app with a plain postgresql:// URL."""
    pytest.importorskip("psycopg2")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NEON_DATABASE_URL", "DATABASE_URL"))}
    env.update(
        NEON_DATABASE_URL="postgresql://u:p@127.0.0.1:1/db",
        JWT_SECRET_KEY="test-only",
        PYTHONPATH=os.pathsep.join([str(REPO), env.get("PYTHONPATH", "")]),
    )
    result = subprocess.run(
        [sys.executable, "-c", "import api.database as d; print(d.engine.dialect.driver)"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "psycopg2"
