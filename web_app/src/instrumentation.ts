// OpenTelemetry browser tracing — initialized ONCE for the whole app.
//
// Import this module at the very top of the app entry point (`main.tsx`) so the
// tracer provider is registered before any component renders or fires a span.
//
// DEV-SAFETY (hard requirement): with NO collector endpoint configured we do NOT
// register the OTLP exporter at all. Without a span processor, spans are created
// and dropped in-process — zero network POSTs, zero failed-request console spam.
// The exporter (and its batch processor) is wired up *only* when an endpoint env
// var is present, mirroring the API's `setup_telemetry` gating in api/telemetry.py.

import { trace, type Span, type Attributes, SpanStatusCode } from '@opentelemetry/api'
import { WebTracerProvider, BatchSpanProcessor } from '@opentelemetry/sdk-trace-web'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { resourceFromAttributes } from '@opentelemetry/resources'
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from '@opentelemetry/semantic-conventions'

/** Matches the API's naming style (`open-navigator-api`). */
const SERVICE_NAME = 'open-navigator-frontend'

/** Stable tracer name reused for every manual span across the app. */
export const TRACER_NAME = 'open-navigator-frontend'

/**
 * Resolve the OTLP/HTTP traces endpoint from Vite env, if configured.
 * Returns `null` when no collector is set — which keeps dev fully offline.
 */
function resolveOtlpEndpoint(): string | null {
  const env = import.meta.env
  const endpoint =
    env.VITE_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
    env.VITE_OTEL_EXPORTER_OTLP_ENDPOINT ||
    null
  return typeof endpoint === 'string' && endpoint.trim().length > 0 ? endpoint.trim() : null
}

// Guard against double-initialization. Vite HMR can re-evaluate this module, and
// React.StrictMode double-invokes effects — neither should register two providers.
//
// We stash a flag on globalThis so the guard survives module re-evaluation.
const GLOBAL_FLAG = '__openNavigatorOtelInitialized__'

function initTelemetry(): void {
  const g = globalThis as Record<string, unknown>
  if (g[GLOBAL_FLAG]) return
  g[GLOBAL_FLAG] = true

  const endpoint = resolveOtlpEndpoint()

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: SERVICE_NAME,
    [ATTR_SERVICE_VERSION]: import.meta.env.VITE_APP_VERSION || '0.0.0',
  })

  // CRITICAL dev-safety: only attach an exporter/processor when a collector is
  // configured. With an empty `spanProcessors` array the provider creates spans
  // but never ships them anywhere — no network calls, no console errors.
  const spanProcessors = endpoint
    ? [new BatchSpanProcessor(new OTLPTraceExporter({ url: endpoint }))]
    : []

  const provider = new WebTracerProvider({ resource, spanProcessors })

  // Register as the global provider. We intentionally use the default context
  // manager (no ZoneContextManager dep) and add no auto-instrumentations, to
  // keep the dependency surface minimal and avoid double-tracing the existing
  // native-fetch client in `lib/api.ts`. All app spans are created manually.
  provider.register()

  if (endpoint && import.meta.env.DEV) {
    console.info(`[otel] exporting traces to ${endpoint} (service=${SERVICE_NAME})`)
  }
}

initTelemetry()

/** Shared tracer for manual instrumentation across the app. */
export const tracer = trace.getTracer(TRACER_NAME)

/**
 * Run `fn` inside a span named `name`, recording errors and always ending the
 * span. Works for both sync and async `fn`. Attributes are low-cardinality by
 * convention — never pass raw user input (query strings, etc.).
 */
export function withSpan<T>(
  name: string,
  fn: (span: Span) => T,
  attributes?: Attributes,
): T {
  const span = tracer.startSpan(name, attributes ? { attributes } : undefined)
  try {
    const result = fn(span)
    if (result instanceof Promise) {
      return result
        .catch((err: unknown) => {
          recordSpanError(span, err)
          throw err
        })
        .finally(() => span.end()) as unknown as T
    }
    span.end()
    return result
  } catch (err) {
    recordSpanError(span, err)
    span.end()
    throw err
  }
}

function recordSpanError(span: Span, err: unknown): void {
  span.setStatus({ code: SpanStatusCode.ERROR })
  if (err instanceof Error) span.recordException(err)
}
