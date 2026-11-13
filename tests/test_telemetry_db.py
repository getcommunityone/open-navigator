"""Every database query gets an OpenTelemetry span (#258).

The API reaches Postgres through asyncpg, psycopg2 and SQLAlchemy. ``instrument_databases``
instruments all three so a slow request shows which query cost the time. The SQLAlchemy tests
run real queries (SQLite in memory) and find their spans, one of them through the API's own
engine after importing ``api.main``; asyncpg and psycopg2 need a live Postgres for that, so for
them the test checks that the instrumentor is active.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk")
sqlalchemy = pytest.importorskip("sqlalchemy")

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from api import telemetry

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTRUMENTORS = {
    "AsyncPGInstrumentor": "opentelemetry.instrumentation.asyncpg",
    "Psycopg2Instrumentor": "opentelemetry.instrumentation.psycopg2",
    "SQLAlchemyInstrumentor": "opentelemetry.instrumentation.sqlalchemy",
}


def _instrumentor(class_name: str):
    module = importlib.import_module(INSTRUMENTORS[class_name])
    return getattr(module, class_name)()


def _uninstrument_all() -> None:
    for class_name in INSTRUMENTORS:
        instrumentor = _instrumentor(class_name)
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.uninstrument()


@pytest.fixture()
def exporter():
    """A private tracer provider whose finished spans land in memory, from a clean start: importing ``api``
    loads ``api.main`` (``api/__init__.py``), whose setup_telemetry has already instrumented the drivers against
    the app's own provider. Undone after the test."""
    _uninstrument_all()
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    yield provider, memory
    _uninstrument_all()


def test_every_driver_is_instrumented(exporter):
    provider, _ = exporter
    active = telemetry.instrument_databases(tracer_provider=provider)
    for class_name in INSTRUMENTORS:
        driver = INSTRUMENTORS[class_name].rsplit(".", 1)[-1]
        if importlib.util.find_spec(driver) is None:
            continue  # the driver itself isn't installed here; production installs all three
        assert class_name in active, f"{class_name} not active"
        assert _instrumentor(class_name).is_instrumented_by_opentelemetry


def test_a_sqlalchemy_query_gets_its_own_span(exporter):
    provider, memory = exporter
    telemetry.instrument_databases(tracer_provider=provider)
    engine = sqlalchemy.create_engine("sqlite://")  # created after instrumenting, like the API's lazy engines
    with engine.connect() as connection:
        assert connection.execute(sqlalchemy.text("select 1")).scalar() == 1
    spans = [s for s in memory.get_finished_spans() if s.attributes.get("db.system") == "sqlite"]
    assert spans, "the query produced no database span"
    assert "select 1" in spans[-1].attributes.get("db.statement", "").lower()


def test_instrumenting_twice_is_harmless(exporter):
    provider, _ = exporter
    first = telemetry.instrument_databases(tracer_provider=provider)
    second = telemetry.instrument_databases(tracer_provider=provider)
    assert first == second


def test_a_missing_instrumentation_package_warns_and_carries_on(exporter, monkeypatch):
    provider, _ = exporter
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.asyncpg", None)  # import now fails
    active = telemetry.instrument_databases(tracer_provider=provider)
    assert "AsyncPGInstrumentor" not in active
    assert "SQLAlchemyInstrumentor" in active


END_TO_END = """
import json
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import api.main  # noqa: F401 - as uvicorn loads it: setup_telemetry, then the routes and api.database
import sqlalchemy
import api.database as db
memory = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(memory))
with trace.get_tracer("test").start_as_current_span("request") as request:
    with db.engine.connect() as connection:
        connection.execute(sqlalchemy.text("select 42"))
spans = [{"name": s.name, "system": s.attributes.get("db.system"), "parent": s.parent.span_id if s.parent else None}
         for s in memory.get_finished_spans()]
print(json.dumps({"request": request.get_span_context().span_id, "spans": spans}))
"""


def test_the_apis_own_engine_is_traced_under_the_request():
    """End to end, in a fresh interpreter: import api.main, then query through api.database's engine inside a
    stand-in request span. This fails if a module that binds create_engine (api.database does) is ever imported
    before setup_telemetry runs: its engine would quietly go untraced."""
    env = {k: v for k, v in os.environ.items() if k not in ("NEON_DATABASE_URL_DEV", "NEON_DATABASE_URL")}
    env["DATABASE_URL"] = "sqlite://"  # in memory: nothing is written
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    done = subprocess.run([sys.executable, "-c", END_TO_END], cwd=REPO_ROOT, env=env, capture_output=True,
                          text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    queries = [s for s in out["spans"] if s["system"] == "sqlite" and s["name"] != "connect"]
    assert queries, f"no query span: {out['spans']}"
    assert all(s["parent"] == out["request"] for s in queries), "query spans aren't under the request span"
