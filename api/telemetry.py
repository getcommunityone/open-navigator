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

    _INSTRUMENTED = True
    logger.success("✅ OpenTelemetry instrumentation enabled for {}", SERVICE_NAME)
