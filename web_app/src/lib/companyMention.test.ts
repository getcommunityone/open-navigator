import { describe, expect, it } from 'vitest'
import { companyMentionLabel, companyMentionLink } from './companyMention'

describe('companyMentionLabel', () => {
  it('says "Named in the meeting" for a passage of the decision\'s own meeting', () => {
    expect(companyMentionLabel({ evidence_source: 'meeting_passage' })).toBe('Named in the meeting')
  })

  it('keeps "Company named" for the decision\'s own text and for an older API answer', () => {
    expect(companyMentionLabel({ evidence_source: 'decision_text' })).toBe('Company named')
    expect(companyMentionLabel({})).toBe('Company named')
  })
})

describe('companyMentionLink', () => {
  const url = 'https://www.youtube.com/watch?v=LGJDZSrSoBU&t=2082s'

  it('links a meeting-passage mention to the recording', () => {
    expect(companyMentionLink({ evidence_source: 'meeting_passage', jump_url: url })).toBe(url)
  })

  it('has no link when the API gave none, or for the decision\'s own text', () => {
    expect(companyMentionLink({ evidence_source: 'meeting_passage', jump_url: null })).toBeNull()
    expect(companyMentionLink({ evidence_source: 'decision_text', jump_url: url })).toBeNull()
  })
})
