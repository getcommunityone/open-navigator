import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import { CAPTION_COPY, pickCaption, withTopicBlank } from './storyCaption'
import type { StoryTitlePart } from './dataStory'

// #1290 (owner screenshot, 27 Nov 2026: "America mostly wants fluoridation ended ( water fluoridation ▾)."): in every topic's
// headline the topic control is the noun in the sentence: one control, no bracket beside it, and the topic not repeated.
// Test stand-ins shaped like caption-facts, not warehouse figures.
const nat = { stateName: null, city: null }
const facts = (against: number, pro: number, split: number): TopicCaptionFacts =>
  ({
    topic: 'x', topic_id: 1, scope: { level: 'national', state_code: null, state: null, city: null }, meetings: 1000,
    states: [], top_state: null, ratio_to_next: null, place: null, places: null, speakers: null, lean_meetings: 1000,
    public_against_meetings: against, public_against_states: 5, public_for_meetings: pro, public_split_meetings: split,
    public_silent_meetings: 1000 - against - pro - split, disagreement_meetings: 0, disagreement_states: 0, wider: [],
  }) as TopicCaptionFacts

const render = (t: StoryTitlePart[], topic: string) => t.map((p) => (typeof p === 'string' ? p : p.blank === 'topic' ? `[${topic}]` : 'America')).join('')

describe('every headline puts the topic control in the sentence', () => {
  const topics = Object.entries(CAPTION_COPY).filter(([, c]) => c.facts)
  for (const [key, copy] of topics) {
    for (const [side, f] of [['against', facts(300, 10, 10)], ['for', facts(10, 300, 10)], ['split', facts(100, 100, 100)]] as const) {
      it(`${key}, ${side}`, () => {
        const c = pickCaption(key, f, nat)
        const t = withTopicBlank(c.template, copy.topic)
        const text = render(t, copy.topic)
        expect(t.filter((p) => typeof p !== 'string' && p.blank === 'topic')).toHaveLength(1)
        expect(text).not.toMatch(/\(\s*\[|\]\s*\)/)
        expect(text).not.toContain('(')
        // The topic's own words appear once: inside the control.
        const outside = text.replace(`[${copy.topic}]`, '')
        for (const w of copy.topic.toLowerCase().split(/\s+/).filter((w) => w.length > 3 && w !== 'and')) {
          expect(outside.toLowerCase()).not.toContain(w.replace(/s$/, ''))
        }
      })
    }
  }
})
