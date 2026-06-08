// Native fetch-based API client - No axios dependency!
// Handles relative URLs correctly without HTTP/HTTPS conversion issues

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
        if (value !== undefined && value !== null) {
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
