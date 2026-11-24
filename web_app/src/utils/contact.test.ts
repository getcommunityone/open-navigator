import { describe, expect, it } from 'vitest'
import { CONTACT_EMAIL, contactMailto } from './contact'

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
