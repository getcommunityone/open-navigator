import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import { CLASSIFIER_SOURCE, recordedEvidence, speakersOwnWordsLine } from './stanceEvidence'
import { topicPositions } from './topicPositions'

// #1391: speakers' own words read by the classifier are a separate, labelled source. Test stand-in counts, not warehouse figures.
const facts = (classifier_speakers: TopicCaptionFacts['classifier_speakers']) =>
  ({ topic: 'data-centers', topic_id: 100001, classifier_speakers } as unknown as TopicCaptionFacts)

describe('speakers own words (classifier)', () => {
  it('labels the source and uses the topic words, no zero side', () => {
    const e = recordedEvidence(facts({ source: 'x', for: 4, against: 9, concerns_only: 3, no_position: 1, meetings: 6 }))
    expect(speakersOwnWordsLine(e, topicPositions('data-centers'))).toBe(
      `${CLASSIFIER_SOURCE}: 9 against data centers · 4 for data centers · 3 concerns only (17 speakers)`,
    )
    const e2 = recordedEvidence(facts({ source: 'x', for: 0, against: 2, concerns_only: 0, no_position: 0, meetings: 1 }))
    expect(speakersOwnWordsLine(e2)).toBe(`${CLASSIFIER_SOURCE}: 2 against (2 speakers)`)
  })

  it('is null when nothing was read, and never invents a count', () => {
    expect(speakersOwnWordsLine(recordedEvidence(facts(null)))).toBeNull()
    expect(speakersOwnWordsLine(recordedEvidence(facts({ source: 'x', for: 0, against: 0, concerns_only: 0, no_position: 0, meetings: 0 })))).toBeNull()
    expect(recordedEvidence(facts(undefined)).classifier).toBeNull()
  })

  it('counts speakers who took no side in the total, never as a side', () => {
    const e = recordedEvidence(facts({ source: 'x', for: 0, against: 0, concerns_only: 0, no_position: 3, meetings: 2 }))
    expect(speakersOwnWordsLine(e)).toBe(`${CLASSIFIER_SOURCE}: no side taken (3 speakers)`)
  })
})
