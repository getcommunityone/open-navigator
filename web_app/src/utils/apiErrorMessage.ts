/**
 * The human-readable reason in an API error response (#888).
 *
 * FastAPI's own errors carry it under `detail`; this API's error handler returns `message` (and a short `error`).
 * Validation errors are a list of `{ msg }`. Falls back to the status code only when the body says nothing.
 */
export function apiErrorMessage(body: unknown, status: number): string {
  const fromValue = (v: unknown): string => {
    if (typeof v === 'string') return v.trim()
    if (Array.isArray(v)) {
      return v
        .map((x) => (x && typeof x === 'object' && 'msg' in x ? String((x as { msg: unknown }).msg) : fromValue(x)))
        .filter(Boolean)
        .join('; ')
    }
    if (v && typeof v === 'object') {
      const o = v as Record<string, unknown>
      return fromValue(o.detail) || fromValue(o.message) || fromValue(o.error)
    }
    return ''
  }
  return fromValue(body) || `HTTP ${status}`
}

/** An error that keeps the HTTP status, so a caller can tell "nothing stored" (404) from a failure. */
export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
