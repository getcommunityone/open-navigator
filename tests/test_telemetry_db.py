"""Every database query gets an OpenTelemetry span (#258).

The API reaches Postgres through asyncpg, psycopg2 and SQLAlchemy. ``instrument_databases``
instruments all three so a slow request shows which query cost the time. The SQLAlchemy test
runs a real query (SQLite in memory) and finds its span; asyncpg and psycopg2 need a live
Postgres for that, so for them the test checks that the instrumentor is active.
"""

from __future__ import annotations

import importlib
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

INSTRUMENTORS = {
    "AsyncPGInstrumentor": "opentelemetry.instrumentation.asyncpg",
    "Psycopg2Instrumentor": "opentelemetry.instrumentation.psycopg2",
    "SQLAlchemyInstrumentor": "opentelemetry.instrumentation.sqlalchemy",
}


def _instrumentor(class_name: str):
    module = importlib.import_module(INSTRUMENTORS[class_name])
    return getattr(module, class_name)()


@pytest.fixture()
def exporter():
    """A private tracer provider whose finished spans land in memory; undone after the test."""
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    yield provider, memory
    for class_name in INSTRUMENTORS:
        instrumentor = _instrumentor(class_name)
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.uninstrument()


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


def test_setup_telemetry_instruments_the_databases():
    source = importlib.util.find_spec("api.telemetry").origin
    text = Path(source).read_text(encoding="utf-8")
    setup = text[text.index("def setup_telemetry"):]
    assert "instrument_databases(" in setup
