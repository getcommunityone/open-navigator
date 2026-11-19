// The number beside a topic on Browse Topics: meetings whose transcript mentions the topic, in the scope the API was
// asked for (national, or the state). It is never the national CivicSearch snippet count, which is a different
// measure and does not change when the user picks a state (#504).

/** "1,234 meetings", "1 meeting", or "—" when the API sent no count (never a stand-in number). */
export function topicMeetingCountLabel(count: number | null | undefined): string {
  if (typeof count !== 'number' || !Number.isFinite(count)) return '—'
  return `${count.toLocaleString('en-US')} ${count === 1 ? 'meeting' : 'meetings'}`
}

/** Hover text naming the scope the count was computed for; it must match the data, so a city is never named here. */
export function topicCountTitle(stateCode?: string): string {
  return `Meetings whose transcript mentions this topic ${stateCode ? `in ${stateCode}` : 'nationally'}`
}
