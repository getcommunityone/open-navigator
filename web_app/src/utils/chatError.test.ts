import { describe, expect, it } from 'vitest'
import { chatErrorMessage } from './chatError'

describe('chatErrorMessage', () => {
  it("shows the server's reason from this API's error body", () => {
    const r = chatErrorMessage({ response: { status: 503, data: { error: 'x', message: 'Chat is not set up on this site yet.' } } })
    expect(r.kind).toBe('server')
    expect(r.text).toMatch(/^Chat is not set up on this site yet\./)
    expect(r.text).toContain('Contact us')
  })

  it("shows FastAPI's detail when that is what came back", () => {
    const r = chatErrorMessage({ response: { status: 429, data: { detail: 'Please wait a few seconds between questions.' } } })
    expect(r.text).toMatch(/^Please wait a few seconds between questions\./)
  })

  it('names the status when the body says nothing', () => {
    expect(chatErrorMessage({ response: { status: 500, data: null } }).text).toMatch(/^The chat could not answer \(error 500\)\./)
    expect(chatErrorMessage({ response: { status: 429, data: {} } }).text).toMatch(/^Too many questions/)
  })

  it('tells a timeout from a lost connection', () => {
    expect(chatErrorMessage({ name: 'AbortError' }).kind).toBe('timeout')
    expect(chatErrorMessage(new TypeError('Failed to fetch')).kind).toBe('offline')
    expect(chatErrorMessage(new TypeError('Failed to fetch')).text).toMatch(/could not be reached/)
  })
})
