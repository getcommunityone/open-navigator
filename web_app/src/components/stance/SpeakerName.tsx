/** A speaker's name with how we know it (#1386): high shows the name, medium marks it "likely", low does not show it. */

export type AttributionTier = 'high' | 'medium' | 'low'

export interface Attribution {
  method?: string | null
  confidence?: number | null
  tier?: string | null
  evidence?: string | null
}

/** One plain sentence per attribution method, for the tooltip and the "How we know" panel. */
export const METHOD_SENTENCES: Record<string, string> = {
  self_intro: 'Matched from the speaker introducing themselves',
  chair_call: 'Matched from the chair calling the speaker',
  caption_marker_turn: 'A speaker change in the captions; no name was said',
  official_roster_match: "Matched to the government's own list of officials",
  ai_extraction_held_by: "Read from the meeting analysis's record of who held this view",
  voice_diarization: 'Matched by voice',
}

export function methodSentence(method: string | null | undefined): string | null {
  return method ? (METHOD_SENTENCES[method] ?? null) : null
}

export function attributionTier(a: Attribution): AttributionTier | null {
  return a.tier === 'high' || a.tier === 'medium' || a.tier === 'low' ? a.tier : null
}

/** What to show for the name: the name (high), the name marked likely (medium), or nothing but "not identified" (low). */
export function nameDisplay(
  name: string | null | undefined,
  a: Attribution,
): { text: string; likely: boolean; identified: boolean } {
  const tier = attributionTier(a)
  if (!name || tier === 'low') return { text: 'Speaker not identified', likely: false, identified: false }
  return { text: name, likely: tier === 'medium', identified: true }
}

export function HowWeKnow({ a }: { a: Attribution }) {
  const sentence = methodSentence(a.method)
  if (!sentence) return null
  const pct = typeof a.confidence === 'number' ? ` (${a.tier ?? 'unrated'}, ${Math.round(a.confidence * 100)}%)` : ''
  return (
    <details className="speaker-how">
      <summary>How we know</summary>
      <span>
        {sentence}
        {pct}.{a.evidence ? <> Cue: {a.evidence}</> : null}
      </span>
    </details>
  )
}

export function SpeakerName({
  name,
  attribution,
  possibleName,
}: {
  name: string | null | undefined
  attribution: Attribution
  possibleName?: string | null
}) {
  const d = nameDisplay(name, attribution)
  const sentence = methodSentence(attribution.method)
  return (
    <span className="speaker-name">
      <strong>{d.text}</strong>
      {d.likely && (
        <span className="speaker-likely" title={sentence ? `${sentence}.` : undefined}>
          {' '}
          likely
        </span>
      )}
      {!d.identified && possibleName && (
        <details className="speaker-how">
          <summary>Possibly</summary>
          <span>{possibleName}</span>
        </details>
      )}{' '}
      <HowWeKnow a={attribution} />
    </span>
  )
}
