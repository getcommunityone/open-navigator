// The home page's story -> outcomes strip (#1302): its cards and where each one opens.

export interface OutcomeCard {
  key: string
  eyebrow: string
  /** The one real number, or null while loading / unavailable (shown as a dash, never a stand-in). */
  value: number | null
  line: string
  /** The story screen the card opens (?screen=). */
  screen: string
  /** The first, most prominent card. */
  lead?: boolean
}

/** `/stories/<topic>?state=GA&city=…&screen=upcoming`: the story at the home page's place, on one screen. */
export function outcomeCardHref(topic: string, scope: { stateCode: string | null; city: string | null }, screen: string): string {
  const q = new URLSearchParams()
  if (scope.stateCode) q.set('state', scope.stateCode)
  if (scope.stateCode && scope.city) q.set('city', scope.city)
  q.set('screen', screen)
  return `/stories/${encodeURIComponent(topic)}?${q.toString()}`
}
