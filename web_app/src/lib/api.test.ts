// Every API request gets one `api.request` client span and carries a `traceparent` header, so the API's request
// span joins the browser's trace (#260). The span keeps the path and never the query string: an address search
// sends the typed address as `q`.
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { SpanStatusCode } from '@opentelemetry/api'
import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
  WebTracerProvider,
} from '@opentelemetry/sdk-trace-web'

// Registered before the client (and the app's own instrumentation) is imported, so this provider holds the global
// slot and its spans land in memory.
const exporter = new InMemorySpanExporter()
new WebTracerProvider({ spanProcessors: [new SimpleSpanProcessor(exporter)] }).register()

type Sent = { url: string; headers: Headers }
const sent: Sent[] = []
let api: typeof import('./api').default
let tracedFetch: typeof import('./api').tracedFetch

beforeAll(async () => {
  vi.stubGlobal('localStorage', { getItem: () => null, removeItem: () => undefined })
  vi.stubGlobal('location', { origin: 'https://navigator.example' })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL, init: RequestInit = {}) => {
      const url = String(input)
      sent.push({ url, headers: new Headers(init.headers) })
      if (url.includes('/offline')) throw new TypeError('Failed to fetch')
      const status = url.includes('/missing') ? 404 : 200
      return new Response(JSON.stringify({ ok: status === 200 }), {
        status,
        headers: { 'content-type': 'application/json' },
      })
    }),
  )
  ;({ default: api, tracedFetch } = await import('./api'))
})

afterEach(() => {
  exporter.reset()
  sent.length = 0
})

function onlySpan() {
  const spans = exporter.getFinishedSpans()
  expect(spans).toHaveLength(1)
  return spans[0]
}

describe('api.request spans', () => {
  it('records the method, the path and the status, and never the query string', async () => {
    await api.get('/addresses/search', { params: { q: '12 Elm Street' } })
    const span = onlySpan()
    expect(span.name).toBe('api.request')
    expect(span.attributes).toEqual({
      'http.request.method': 'GET',
      'url.path': '/api/addresses/search',
      'http.response.status_code': 200,
    })
    expect(JSON.stringify(span.attributes)).not.toMatch(/Elm|\?|q=/)
    expect(sent[0].url).toBe('/api/addresses/search?q=12+Elm+Street') // the request itself is unchanged
  })

  it("sends traceparent naming the request's own span, so the API joins the trace", async () => {
    await api.get('/states')
    const { traceId, spanId } = onlySpan().spanContext()
    expect(sent[0].headers.get('traceparent')).toBe(`00-${traceId}-${spanId}-01`)
  })

  it('sends no traceparent to another origin', async () => {
    await api.get('https://tiles.example.org/states.json')
    await tracedFetch('https://tiles.example.org/counties.json')
    expect(sent.map((s) => s.headers.get('traceparent'))).toEqual([null, null])
  })

  it('marks an error status as an error', async () => {
    await expect(api.get('/missing')).rejects.toMatchObject({ response: { status: 404 } })
    const span = onlySpan()
    expect(span.status.code).toBe(SpanStatusCode.ERROR)
    expect(span.attributes['http.response.status_code']).toBe(404)
  })

  it('ends the span as an error when the request never gets a response', async () => {
    await expect(api.get('/offline')).rejects.toThrow('Failed to fetch')
    const span = onlySpan()
    expect(span.status.code).toBe(SpanStatusCode.ERROR)
    expect(span.attributes).toEqual({ 'http.request.method': 'GET', 'url.path': '/api/offline' })
  })
})

describe('tracedFetch, for code that calls fetch directly', () => {
  it('traces an API call the same way and returns the response unchanged', async () => {
    const response = await tracedFetch('/api/batch-jobs/launch?dry_run=1', {
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
    })
    expect(response.status).toBe(200)
    const span = onlySpan()
    expect(span.attributes).toEqual({
      'http.request.method': 'POST',
      'url.path': '/api/batch-jobs/launch',
      'http.response.status_code': 200,
    })
    const { traceId, spanId } = span.spanContext()
    expect(sent[0].headers.get('traceparent')).toBe(`00-${traceId}-${spanId}-01`)
    expect(sent[0].headers.get('content-type')).toBe('application/json') // the caller's headers are kept
  })
})
