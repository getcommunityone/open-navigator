// Words for what is coming up on a topic (#1302), shared by the story screen, the data center story and the home scroller.
import type { TopicUpcomingResponse, UpcomingItem } from '../api/topicUpcoming'

const fmt = (n: number) => n.toLocaleString('en-US')

/** "Dec 15, 2026" from an ISO date (read at noon so no time zone moves the day). */
export function upcomingDate(iso: string | null | undefined, withYear = true): string | null {
  if (!iso) return null
  const t = new Date(`${iso.slice(0, 10)}T12:00:00`)
  if (Number.isNaN(t.getTime())) return null
  return t.toLocaleDateString('en-US', withYear ? { month: 'short', day: 'numeric', year: 'numeric' } : { month: 'short', day: 'numeric' })
}

/** The place an item happens: "Savannah, GA". */
export function upcomingPlace(i: Pick<UpcomingItem, 'jurisdiction_name' | 'state_code'>): string {
  return [i.jurisdiction_name, i.state_code].filter(Boolean).join(', ')
}

/** What the item is, in a word or two. */
export function upcomingKindLabel(i: Pick<UpcomingItem, 'kind' | 'match_basis'>): string {
  if (i.kind === 'hearing') return 'Public hearing'
  if (i.kind === 'deadline') return 'Comment deadline'
  if (i.kind === 'bill_action') return 'Bill action'
  return i.match_basis === 'agenda_text' ? 'On the agenda' : 'Scheduled meeting'
}

/** Why it is listed: the reader must see the evidence's basis, never just a date. */
export function upcomingBasisNote(i: UpcomingItem, topic: string): string {
  if (i.match_basis === 'agenda_text') return `The posted agenda names ${topic}.`
  if (i.match_basis === 'official_notice') return `The official notice lists it${i.tentative ? ' (the date is tentative)' : ''}.`
  const when = upcomingDate(i.prior_meeting_date)
  return `Agenda not posted yet. ${i.jurisdiction_name ?? 'This government'} discussed ${topic}${when ? ` on ${when}` : ''}:`
}

/** "Nothing upcoming on record for Georgia." */
export function nothingUpcoming(label: string): string {
  return label === 'National' ? 'Nothing upcoming on record yet.' : `Nothing upcoming on record for ${label}.`
}

/** The screen's headline: what's next, counted, or the honest empty line. */
export function upcomingHeadline(d: TopicUpcomingResponse | undefined, topic: string, label: string): string {
  if (!d) return `What's coming up on ${topic}.`
  const where = label === 'National' ? '' : ` in ${label}`
  if (d.total > 0) {
    const first = d.items[0]
    const soon = first ? upcomingDate(first.date, false) : null
    const n = d.total
    return `${fmt(n)} ${n === 1 ? 'meeting or hearing' : 'meetings and hearings'} on the calendar${where} where ${topic} could come up${soon ? `, the next on ${soon}` : ''}.`
  }
  const bills = d.pending_bills.total
  if (bills > 0) {
    return `${nothingUpcoming(label).replace(/\.$/, '')}, but ${fmt(bills)} state ${bills === 1 ? 'bill is' : 'bills are'} still open.`
  }
  return nothingUpcoming(label)
}

/** One line for the home card: the soonest item, or why there is none. */
export function upcomingCardLine(d: TopicUpcomingResponse | undefined, label: string): string {
  if (!d) return ''
  const first = d.items[0]
  if (first) return `Next: ${upcomingPlace(first)}, ${upcomingDate(first.date, false)}`
  if (d.broader && d.broader.total > 0) return `${nothingUpcoming(label).replace(/\.$/, '')}; ${fmt(d.broader.total)} ${d.broader.label === 'National' ? 'nationally' : `in ${d.broader.label}`}.`
  return nothingUpcoming(label)
}

/** The href one level up from a story or home scope, keeping the screen: city -> state, state -> national. */
export function broaderHref(base: string, broader: TopicUpcomingResponse['broader'], extra = ''): string | null {
  if (!broader) return null
  const q = new URLSearchParams()
  if (broader.state_code) q.set('state', broader.state_code)
  const s = q.toString()
  const tail = extra ? (s ? `&${extra}` : extra) : ''
  return `${base}${s || tail ? '?' : ''}${s}${tail}`
}
