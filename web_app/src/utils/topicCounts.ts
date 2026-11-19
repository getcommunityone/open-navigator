// The number beside a topic on Browse Topics: meetings whose transcript mentions the topic, in the scope the API was
// asked for (national, state, or city). It is never the national CivicSearch snippet count (#504 / #590).

/** "1,234 meetings", "1 meeting", or "—" when the API sent no count (never a stand-in number). */
export function topicMeetingCountLabel(count: number | null | undefined): string {
  if (typeof count !== 'number' || !Number.isFinite(count)) return '—'
  return `${count.toLocaleString('en-US')} ${count === 1 ? 'meeting' : 'meetings'}`
}

/** Hover text naming the scope the count was computed for; must match the filter that produced the number. */
export function topicCountTitle(stateCode?: string, cityName?: string): string {
  if (cityName && stateCode) {
    return `Meetings whose transcript mentions this topic in ${cityName}, ${stateCode}`
  }
  return `Meetings whose transcript mentions this topic ${stateCode ? `in ${stateCode}` : 'nationally'}`
}
