"""
OpenTelemetry bootstrap for the Open Navigator FastAPI service.

Per the CLAUDE.md observability spec: instrument the app at startup via
``FastAPIInstrumentor``, wrap discrete operations (DB queries, external calls,
enrichment) in spans, and export to an OTLP collector — falling back to a
console exporter in development.

Usage (once, at app construction):

    from api.telemetry import setup_telemetry, tracer

    setup_telemetry(app)

    with tracer.start_as_current_span("operation-name") as span:
        span.set_attribute("key", value)

Exporter selection is driven by env:
- If ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``)
  is set, traces are batched and exported over OTLP/HTTP to that collector.
- Else if ``OTEL_CONSOLE_EXPORT`` is truthy, spans are printed to the console via
  a *batched* processor (off the request path) — opt-in because it's noisy.
- Otherwise (the local/dev default) tracing stays active but no exporter is
  attached, so the terminal stays clean and request handling isn't slowed by
  blocking span export.

``setup_telemetry`` is idempotent: calling it more than once is a no-op.
"""
from __future__ import annotations

import importlib
import os

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

# Canonical service identity surfaced on every span / trace.
SERVICE_NAME = "open-navigator-api"

# Module-level tracer — import this wherever you need to open spans
# (e.g. the search dispatcher and per-type DB queries).
tracer = trace.get_tracer(__name__)

# Guard so repeated startup hooks (uvicorn reload, multiple app imports) don't
# stack duplicate TracerProviders / processors.
_INSTRUMENTED = False

# The database drivers the API uses, each with its OpenTelemetry instrumentor.
# asyncpg is patched at the class level, so pools made before or after are traced;
# psycopg2 and SQLAlchemy patch connect()/create_engine(), which is why
# setup_telemetry runs before api/main.py imports any route module (#258).
#
# The third field skips the instrumentor's declared version range. The SQLAlchemy
# instrumentor (0.63b0) declares sqlalchemy < 2.1, but requirements.txt allows any
# 2.x and pip resolves 2.1.8, where it would otherwise refuse to instrument. It works
# on 2.1.8 (tests/test_telemetry_db.py runs a real query and checks its span).
_DB_INSTRUMENTORS: tuple[tuple[str, str, bool], ...] = (
    ("opentelemetry.instrumentation.asyncpg", "AsyncPGInstrumentor", False),
    ("opentelemetry.instrumentation.psycopg2", "Psycopg2Instrumentor", False),
    ("opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor", True),
)


def instrument_databases(tracer_provider=None) -> list[str]:
    """Give every database query its own client span, under the request that ran it.

    Instruments asyncpg, psycopg2 and SQLAlchemy once each (instrumentors are
    singletons, so a second call changes nothing) and returns the names of the
    instrumentors now active. Spans carry the SQL text the driver sends; the API's
    queries pass values as parameters, and asyncpg's parameter capture stays off.
    Tracing is optional: a missing package or driver logs a warning and the API
    carries on.
    """
    active: list[str] = []
    for module_name, class_name, skip_dep_check in _DB_INSTRUMENTORS:
        try:
            instrumentor = getattr(importlib.import_module(module_name), class_name)()
        except ImportError as exc:
            logger.warning(
                "OpenTelemetry: {} isn't installed, so those queries won't be traced ({})",
                class_name,
                exc,
            )
            continue
        if not instrumentor.is_instrumented_by_opentelemetry:
            options: dict = {"skip_dep_check": True} if skip_dep_check else {}
            if tracer_provider is not None:
                options["tracer_provider"] = tracer_provider
            instrumentor.instrument(**options)
        if instrumentor.is_instrumented_by_opentelemetry:
            active.append(class_name)
        else:  # instrument() skips quietly when the driver itself is missing
            logger.warning("OpenTelemetry: {} skipped (its driver isn't installed)", class_name)
    return active


def _resolve_otlp_endpoint() -> str | None:
    """Return the configured OTLP endpoint, or None for dev/console mode.

    Honors the standard OTEL env vars so a collector can be wired in purely
    through the environment with no code change.
    """
    return (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or None
    )


def _console_export_enabled() -> bool:
    """Whether to print spans to the console (opt-in, off by default).

    The console exporter is useful for eyeballing traces in dev, but it's noisy
    (a JSON blob per span) and — with a synchronous processor — does blocking
    stdout I/O on the asyncio event loop, which stalls request handling. So it's
    now opt-in: set ``OTEL_CONSOLE_EXPORT=1`` to turn it on, and even then we
    batch it off the request path.
    """
    return os.getenv("OTEL_CONSOLE_EXPORT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def setup_telemetry(app) -> None:
    """Configure tracing and instrument the FastAPI ``app``.

    Safe to call exactly once at startup; subsequent calls are ignored. With no
    OTLP endpoint configured it cleanly uses the console exporter (dev default)
    and never attempts a network connection.
    """
    global _INSTRUMENTED
    if _INSTRUMENTED:
        logger.debug("OpenTelemetry already initialized; skipping re-instrument")
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": getattr(app, "version", "0.0.0"),
        }
    )
    provider = TracerProvider(resource=resource)

    endpoint = _resolve_otlp_endpoint()
    if endpoint:
        # Production / collector mode: batch spans off the request path so the
        # exporter never blocks request handling.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        logger.info(
            "📡 OpenTelemetry: exporting traces via OTLP/HTTP to {} (service={})",
            endpoint,
            SERVICE_NAME,
        )
    elif _console_export_enabled():
        # Opt-in dev console exporter. BatchSpanProcessor (not Simple) so span
        # serialization + stdout writes happen on a background thread instead of
        # blocking the event loop when each span ends.
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info(
            "🖥️  OpenTelemetry: console span exporter enabled via "
            "OTEL_CONSOLE_EXPORT (service={}). Spans are batched off the request "
            "path.",
            SERVICE_NAME,
        )
    else:
        # Quiet dev default: tracing context is still active (spans are created
        # and parented correctly) but nothing is exported, so the terminal stays
        # clean and request handling isn't slowed by span export. Set
        # OTEL_EXPORTER_OTLP_ENDPOINT to ship traces, or OTEL_CONSOLE_EXPORT=1 to
        # print them locally.
        logger.info(
            "🔇 OpenTelemetry: no exporter configured — tracing active but spans "
            "not exported (service={}). Set OTEL_EXPORTER_OTLP_ENDPOINT to ship "
            "traces, or OTEL_CONSOLE_EXPORT=1 to print them.",
            SERVICE_NAME,
        )

    trace.set_tracer_provider(provider)

    # Instrument the FastAPI app (adds a server span per request, propagates
    # context, and parents the manual spans we open in the search path).
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)

    # One client span per database query, parented under the request span (#258).
    traced = instrument_databases()
    logger.info("OpenTelemetry: database queries traced via {}", ", ".join(traced) or "none")

    _INSTRUMENTED = True
    logger.success("✅ OpenTelemetry instrumentation enabled for {}", SERVICE_NAME)
