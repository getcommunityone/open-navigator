// Native fetch-based API client - No axios dependency!
// Handles relative URLs correctly without HTTP/HTTPS conversion issues

import {
  context,
  defaultTextMapSetter,
  propagation,
  SpanKind,
  SpanStatusCode,
  trace,
  type Span,
  type TextMapSetter,
} from '@opentelemetry/api'
import { TRACER_NAME } from '../instrumentation'

/** Set `VITE_DEBUG_API=true` in `.env.local` to log every request in dev. */
const DEBUG_API = import.meta.env.VITE_DEBUG_API === 'true'

function apiLog(...args: unknown[]) {
  if (DEBUG_API) console.log(...args)
}

// Environment-aware API base URL with NUCLEAR OPTION for production
let API_BASE_URL: string

if (import.meta.env.PROD) {
  // HARDCODE /api in production — ignore env vars that inject http:// URLs
  API_BASE_URL = '/api'
  if (
    typeof import.meta.env.VITE_API_URL === 'string' &&
    import.meta.env.VITE_API_URL.startsWith('http://')
  ) {
    console.warn('[API] Ignoring insecure VITE_API_URL in production; using /api')
  }
} else {
  API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
  apiLog('[API] Development base URL:', API_BASE_URL)
}

// --- Tracing (#260) ----------------------------------------------------------------------------------------------
// Every request to our API gets one `api.request` client span, opened here and nowhere else, and carries a W3C
// `traceparent` header, so the API's request span and its query spans join the browser's trace. The span keeps the
// path only, never the full URL or the query string: an address search sends the typed address as `q`. Requests to
// any other host get no span and no header.

/** The page's origin, to resolve relative URLs against (a placeholder outside a browser). */
function pageOrigin(): string {
  const origin = typeof location !== 'undefined' ? location.origin : undefined
  return origin && origin !== 'null' ? origin : 'http://localhost'
}

/** Is `url` a request to our API: under the configured base URL, or under `/api` on the page's own origin
 *  (where code calling `fetch` directly sends it; the dev server proxies it)? */
function isApiUrl(url: URL): boolean {
  return [API_BASE_URL, '/api'].some((root) => {
    const base = new URL(root, pageOrigin())
    const basePath = base.pathname.replace(/\/+$/, '')
    return url.origin === base.origin && (url.pathname === basePath || url.pathname.startsWith(`${basePath}/`))
  })
}

const headersSetter: TextMapSetter<Headers> = { set: (carrier, key, value) => carrier.set(key, value) }

/** Open the `api.request` span for a request to our API and add `traceparent` to its headers. Returns undefined,
 *  and touches nothing, for any other URL. */
function startApiSpan(
  method: string,
  input: string | URL,
  headers: Headers | Record<string, string>,
): Span | undefined {
  const url = new URL(String(input), pageOrigin())
  if (!isApiUrl(url)) return undefined
  const span = trace.getTracer(TRACER_NAME).startSpan('api.request', {
    kind: SpanKind.CLIENT,
    attributes: { 'http.request.method': method.toUpperCase(), 'url.path': url.pathname },
  })
  const withSpan = trace.setSpan(context.active(), span)
  if (headers instanceof Headers) propagation.inject(withSpan, headers, headersSetter)
  else propagation.inject(withSpan, headers, defaultTextMapSetter)
  return span
}

function recordStatus(span: Span | undefined, status: number): void {
  span?.setAttribute('http.response.status_code', status)
  if (status >= 400) span?.setStatus({ code: SpanStatusCode.ERROR })
}

/** A request that got no usable response. Only the error's type goes on the span: a message can quote the URL. */
function recordFailure(span: Span | undefined, error: unknown): void {
  span?.setStatus({ code: SpanStatusCode.ERROR, message: error instanceof Error ? error.name : 'error' })
}

/**
 * `fetch`, traced, for code that calls `fetch` directly instead of `api`: a request to our API gets the same span
 * and `traceparent` header as `api`'s requests. It returns the native `Response`, unchanged.
 */
export async function tracedFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const span = startApiSpan(init.method || 'GET', input, headers)
  if (!span) return fetch(input, init)
  try {
    const response = await fetch(input, { ...init, headers })
    recordStatus(span, response.status)
    return response
  } catch (error) {
    recordFailure(span, error)
    throw error
  } finally {
    span.end()
  }
}

// Response type that matches axios structure
interface APIResponse<T> {
  data: T
  status: number
  statusText: string
}

// Upper bound on any single request before it aborts. Keeps a slow/hung backend
// from leaving the UI spinning forever; well above normal response times.
const REQUEST_TIMEOUT_MS = 20000

// Fetch wrapper that mimics axios interface
class APIClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  private async request<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    // Build full URL
    const fullUrl = url.startsWith('http') ? url : `${this.baseURL}${url}`
    
    // 🚨 PRODUCTION SAFETY CHECK: Block any http:// URLs
    if (import.meta.env.PROD && fullUrl.startsWith('http://')) {
      const httpsUrl = fullUrl.replace('http://', 'https://')
      console.error('❌ [API] BLOCKED insecure HTTP request in production:', fullUrl)
      console.error('❌ [API] This would cause Mixed Content errors')
      console.error('❌ [API] Upgrading to HTTPS:', httpsUrl)
      throw new Error(`BLOCKED: Attempted to make insecure HTTP request in production: ${fullUrl}`)
    }
    
    apiLog('[FETCH]', options.method || 'GET', fullUrl)

    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const span = startApiSpan(options.method || 'GET', fullUrl, headers)
    let statusError = false

    // Hard request timeout so a slow/hung backend never leaves the UI spinning
    // forever — the request aborts and rejects, letting callers (React Query)
    // render an error/empty state instead.
    const timeoutController = new AbortController()
    const timeoutId = setTimeout(
      () => timeoutController.abort(new DOMException('Request timed out', 'TimeoutError')),
      REQUEST_TIMEOUT_MS,
    )
    const callerSignal = options.signal as AbortSignal | undefined
    const signal =
      callerSignal && typeof AbortSignal !== 'undefined' && 'any' in AbortSignal
        ? (AbortSignal as any).any([callerSignal, timeoutController.signal])
        : timeoutController.signal

    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
        signal,
      })

      recordStatus(span, response.status)

      // Handle 401 unauthorized
      if (response.status === 401) {
        localStorage.removeItem('auth_token')
      }

      // Parse response
      let data: T
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        data = await response.json()
      } else {
        data = (await response.text()) as unknown as T
      }

      if (!response.ok) {
        statusError = true // already on the span, from the status code
        throw {
          response: {
            data,
            status: response.status,
            statusText: response.statusText,
          },
          message: `HTTP ${response.status}: ${response.statusText}`,
        }
      }

      apiLog('[FETCH]', response.status, fullUrl)
      return {
        data,
        status: response.status,
        statusText: response.statusText,
      }
    } catch (error) {
      if (!statusError) recordFailure(span, error)
      // Normalize an aborted/timed-out request into a clear, finite error so the
      // UI shows "try again" rather than spinning indefinitely.
      if (error instanceof DOMException && (error.name === 'TimeoutError' || error.name === 'AbortError')) {
        const timeoutErr = {
          message: `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s. Please try again.`,
          isTimeout: true,
        }
        console.error('[FETCH] Timeout/abort:', fullUrl)
        throw timeoutErr
      }
      console.error('[FETCH] Error:', fullUrl, error)
      throw error
    } finally {
      clearTimeout(timeoutId)
      span?.end()
    }
  }

  async get<T = any>(
    url: string,
    config?: { params?: Record<string, any>; signal?: AbortSignal },
  ): Promise<APIResponse<T>> {
    // Build query string
    let fullUrl = url
    if (config?.params) {
      const params = new URLSearchParams()
      Object.entries(config.params).forEach(([key, value]) => {
        if (value === undefined || value === null) return
        // Arrays become repeated keys (?k=1&k=2), which FastAPI parses into a
        // List[...] query param. String(value) would send "1,2" and 422.
        if (Array.isArray(value)) {
          value.forEach((v) => {
            if (v !== undefined && v !== null) params.append(key, String(v))
          })
        } else {
          params.append(key, String(value))
        }
      })
      const queryString = params.toString()
      if (queryString) {
        fullUrl = `${url}?${queryString}`
      }
    }

    return this.request<T>(fullUrl, { method: 'GET', signal: config?.signal })
  }

  async post<T = any>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async put<T = any>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>(url, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T = any>(url: string): Promise<APIResponse<T>> {
    return this.request<T>(url, { method: 'DELETE' })
  }

  async patch<T = any>(url: string, data?: any): Promise<APIResponse<T>> {
    return this.request<T>(url, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }
}

// Create and export the API client instance
const api = new APIClient(API_BASE_URL)

/** Resolved API base URL (e.g. "/api") for building absolute proxy/static URLs
 *  outside the client (e.g. a PDF <Document file> or media src). */
export const apiBaseUrl = API_BASE_URL

export default api
