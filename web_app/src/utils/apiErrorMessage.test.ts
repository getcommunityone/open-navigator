import { describe, expect, it } from 'vitest'
import { ApiError, apiErrorMessage } from './apiErrorMessage'

describe('apiErrorMessage (#888)', () => {
  it("reads FastAPI's detail", () => {
    expect(apiErrorMessage({ detail: 'No Lighthouse audit found for this URL' }, 404)).toBe(
      'No Lighthouse audit found for this URL',
    )
  })

  it("reads this API's message when there is no detail", () => {
    const body = { error: 'Not Found', message: 'No Lighthouse audit found for this URL (run the scan).', path: '/api/x' }
    expect(apiErrorMessage(body, 404)).toBe('No Lighthouse audit found for this URL (run the scan).')
  })

  it('joins validation messages', () => {
    expect(apiErrorMessage({ detail: [{ msg: 'Field required' }, { msg: 'Too short' }] }, 422)).toBe(
      'Field required; Too short',
    )
  })

  it('falls back to the status code only when the body says nothing', () => {
    expect(apiErrorMessage(null, 404)).toBe('HTTP 404')
    expect(apiErrorMessage({}, 500)).toBe('HTTP 500')
    expect(apiErrorMessage({ detail: '   ' }, 502)).toBe('HTTP 502')
    expect(apiErrorMessage({ error: 'Bad Gateway' }, 502)).toBe('Bad Gateway')
  })

  it('keeps the status on the error', () => {
    const e = new ApiError('nothing stored', 404)
    expect(e.status).toBe(404)
    expect(e.message).toBe('nothing stored')
    expect(e instanceof Error).toBe(true)
  })
})
