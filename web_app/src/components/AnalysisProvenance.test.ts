import { describe, expect, it } from 'vitest'
import { chosenAmongNote, provenanceFacts } from './AnalysisProvenance'

describe('provenanceFacts (#798)', () => {
  it('lists every recorded fact', () => {
    const facts = provenanceFacts({
      model: 'deepseek-flash',
      generated_at: '2026-11-20T12:00:00',
      tier: 'light',
      prompt_name: 'policy_analysis',
      prompt_version: 'a1b2c3d4e5f6',
      transcript_source: 'youtube captions',
    })
    expect(facts.map((f) => f.label)).toEqual(['Model', 'Generated', 'Analysis', 'Prompt', 'Transcript source'])
    expect(facts.find((f) => f.label === 'Prompt')?.value).toBe('policy_analysis (version a1b2c3d4e5f6)')
  })

  it('leaves out every fact that was not recorded', () => {
    expect(provenanceFacts({ model: 'gemini-2.5-flash' })).toEqual([{ label: 'Model', value: 'gemini-2.5-flash' }])
    expect(provenanceFacts({ model: null, tier: 'unknown', prompt_name: null })).toEqual([])
    expect(provenanceFacts(null)).toEqual([])
  })

  it('shows the prompt name alone when its version was not recorded', () => {
    expect(provenanceFacts({ prompt_name: 'policy_analysis' })).toEqual([
      { label: 'Prompt', value: 'policy_analysis' },
    ])
  })

  it('says which analysis was shown only when several exist', () => {
    expect(chosenAmongNote({ analyses_for_meeting: 1 })).toBeNull()
    expect(chosenAmongNote({})).toBeNull()
    expect(chosenAmongNote({ analyses_for_meeting: 2 })).toContain('2 analyses')
  })
})
