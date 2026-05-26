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

    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
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
      console.error('[FETCH] Error:', fullUrl, error)
      throw error
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

export default api
