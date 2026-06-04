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
- Otherwise (the local/dev default) spans are printed by a console exporter, so
  the API never tries to dial a missing collector or spams connection errors.

``setup_telemetry`` is idempotent: calling it more than once is a no-op.
"""
from __future__ import annotations

import os

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

# Canonical service identity surfaced on every span / trace.
SERVICE_NAME = "open-navigator-api"

# Module-level tracer — import this wherever you need to open spans
# (e.g. the search dispatcher and per-type DB queries).
tracer = trace.get_tracer(__name__)

# Guard so repeated startup hooks (uvicorn reload, multiple app imports) don't
# stack duplicate TracerProviders / processors.
_INSTRUMENTED = False


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
    else:
        # Dev default: print spans to the console, no collector required.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.info(
            "🖥️  OpenTelemetry: no OTLP endpoint set — using console span exporter "
            "(service={}). Set OTEL_EXPORTER_OTLP_ENDPOINT to ship to a collector.",
            SERVICE_NAME,
        )

    trace.set_tracer_provider(provider)

    # Instrument the FastAPI app (adds a server span per request, propagates
    # context, and parents the manual spans we open in the search path).
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)

    _INSTRUMENTED = True
    logger.success("✅ OpenTelemetry instrumentation enabled for {}", SERVICE_NAME)
