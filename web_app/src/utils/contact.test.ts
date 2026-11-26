import { describe, expect, it } from 'vitest'
import { CONTACT_EMAIL, closeChatTarget, contactMailto } from './contact'

describe('contactMailto (#860)', () => {
  it('is a plain mailto without a subject', () => {
    expect(contactMailto()).toBe(`mailto:${CONTACT_EMAIL}`)
    expect(contactMailto('   ')).toBe(`mailto:${CONTACT_EMAIL}`)
  })

  it('encodes the subject', () => {
    expect(contactMailto('Question about Open Navigator & meetings')).toBe(
      `mailto:${CONTACT_EMAIL}?subject=Question%20about%20Open%20Navigator%20%26%20meetings`,
    )
  })
})

describe('closeChatTarget (#879)', () => {
  it('goes back when there is in-app history', () => {
    expect(closeChatTarget('a1b2c3')).toBe(-1)
  })

  it('goes home when the chat was the first page opened', () => {
    expect(closeChatTarget('default')).toBe('/')
    expect(closeChatTarget('')).toBe('/')
  })
})
