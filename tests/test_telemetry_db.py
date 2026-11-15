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
    """A private tracer provider whose finished spans land in memory, from a clean start: another test may have
    imported ``api.main``, whose setup_telemetry has already instrumented the drivers against the app's own
    provider. Undone after the test."""
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


def _run_in_a_fresh_interpreter(script: str) -> dict:
    """Run ``script`` in a new interpreter, with this session's import path and an in-memory database, and return
    the JSON its last line prints."""
    env = {k: v for k, v in os.environ.items() if k not in ("NEON_DATABASE_URL_DEV", "NEON_DATABASE_URL")}
    env["DATABASE_URL"] = "sqlite://"  # in memory: nothing is written
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    done = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True,
                          text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_apis_own_engine_is_traced_under_the_request():
    """End to end, in a fresh interpreter: import api.main, then query through api.database's engine inside a
    stand-in request span. This fails if a module that binds create_engine (api.database does) is ever imported
    before setup_telemetry runs: its engine would quietly go untraced."""
    out = _run_in_a_fresh_interpreter(END_TO_END)
    queries = [s for s in out["spans"] if s["system"] == "sqlite" and s["name"] != "connect"]
    assert queries, f"no query span: {out['spans']}"
    assert all(s["parent"] == out["request"] for s in queries), "query spans aren't under the request span"


ASYNC_ENGINE = """
import asyncio
import json
from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor
import api.main  # noqa: F401 - as uvicorn loads it: setup_telemetry runs first
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

class QuerySpans(SpanProcessor):
    started = ended = 0
    def on_start(self, span, parent_context=None):
        QuerySpans.started += span.name != "connect"
    def on_end(self, span):
        QuerySpans.ended += span.name != "connect"

trace.get_tracer_provider().add_span_processor(QuerySpans())

async def one_query():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.connect() as connection:
        await connection.execute(sqlalchemy.text("select 1"))
    await engine.dispose()

asyncio.run(one_query())
error = None
try:
    SQLAlchemyInstrumentor().uninstrument()
except Exception as exc:  # what broke the exporter fixture above on main (#337)
    error = repr(exc)
print(json.dumps({"started": QuerySpans.started, "ended": QuerySpans.ended, "uninstrument_error": error}))
"""


def test_an_async_engine_is_traced_once():
    """In a fresh interpreter, as uvicorn loads the app: one query on an async engine starts one span and ends it,
    and tracing turns off cleanly. When SQLAlchemy's asyncio extension was first imported after tracing started,
    create_async_engine traced each engine twice: two spans per query, one never ended, and uninstrumenting raised
    (#337)."""
    pytest.importorskip("aiosqlite")
    out = _run_in_a_fresh_interpreter(ASYNC_ENGINE)
    assert out == {"started": 1, "ended": 1, "uninstrument_error": None}
