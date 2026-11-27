// Words for the chain from meeting to outcome (#1314). Counts follow the shared display rule (utils/displayFit, #1289):
// 0 says "No recorded … yet", a few categories are stated in words, never a chart for a handful.
import type { TopicOutcomesResponse } from '../api/topicOutcomes'

const fmt = (n: number) => n.toLocaleString('en-US')
const plural = (n: number, one: string, many: string) => `${fmt(n)} ${n === 1 ? one : many}`

/** "12 opposed, 3 mixed and 1 supportive": the non-zero parts in a fixed order, in words. */
export function partsSentence(parts: [string, number | undefined][]): string {
  const shown = parts.filter(([, n]) => (n ?? 0) > 0).map(([w, n]) => `${fmt(n!)} ${w}`)
  if (shown.length === 0) return ''
  if (shown.length === 1) return shown[0]!
  return `${shown.slice(0, -1).join(', ')} and ${shown[shown.length - 1]}`
}

export type ChainStepId = 'meetings' | 'public' | 'actions' | 'bills' | 'linked_bills' | 'next'

export interface ChainStep {
  id: ChainStepId
  /** The step's short name. */
  label: string
  count: number
  /** One line under the count, or the honest empty line. */
  line: string
  available: boolean
}

/** Each step's number and line, from the response. `actionWords` are the topic's own words for advanced / blocked. */
export function chainSteps(d: TopicOutcomesResponse, topic: string, actionWords: { advanced: string; blocked: string }): ChainStep[] {
  const s = d.steps
  const adv = actionWords.advanced.toLowerCase()
  const blk = actionWords.blocked.toLowerCase()
  return [
    {
      id: 'meetings',
      label: 'Meetings',
      count: s.meetings.count,
      available: s.meetings.available,
      line: s.meetings.count ? `${s.meetings.count === 1 ? 'Meeting' : 'Meetings'} where ${topic} came up.` : `No recorded meetings on ${topic} yet.`,
    },
    {
      id: 'public',
      label: 'The public',
      count: s.public.count,
      available: s.public.available,
      line: s.public.count
        ? `Meetings where the public spoke: ${partsSentence([['mostly opposed', s.public.by_lean.opposed], ['both sides spoke', s.public.by_lean.mixed], ['mostly supportive', s.public.by_lean.supportive]])}.`
        : 'No recorded public comment on it yet.',
    },
    {
      id: 'actions',
      label: 'Officials',
      count: s.actions.count,
      available: s.actions.available,
      line: s.actions.count
        ? `Meetings where the body acted: ${partsSentence([[adv, s.actions.by_outcome.advanced], [blk, s.actions.by_outcome.blocked], ['moratorium', s.actions.by_outcome.moratorium], ['tabled or put off', s.actions.by_outcome.tabled]])}.`
        : 'No recorded votes or delays yet.',
    },
    {
      id: 'bills',
      label: 'State bills',
      count: s.bills.count,
      available: s.bills.available,
      line: s.bills.count
        ? `${partsSentence([['enacted', s.bills.by_status.enacted], ['passed one chamber', s.bills.by_status.passed_chamber], ['pending', s.bills.by_status.pending], ['failed', s.bills.by_status.failed]])}.`
        : 'No recorded state bills yet.',
    },
    {
      id: 'linked_bills',
      label: 'Named a bill',
      count: s.linked_bills.count,
      available: s.linked_bills.available,
      line: s.linked_bills.count
        ? `${s.linked_bills.count === 1 ? 'Meeting' : 'Meetings'} that named ${plural(s.linked_bills.bills, 'state bill', 'state bills')} by number.`
        : 'No recorded meeting named a state bill yet.',
    },
    {
      id: 'next',
      label: "What's next",
      count: s.next.count,
      available: s.next.available,
      line: s.next.count
        ? `${partsSentence([[s.next.upcoming === 1 ? 'meeting or hearing ahead' : 'meetings and hearings ahead', s.next.upcoming], [s.next.pending_bills === 1 ? 'state bill still open' : 'state bills still open', s.next.pending_bills]])}.`
        : 'No upcoming meetings on record, and no open state bill.',
    },
  ]
}

/** The screen's headline: the chain in one sentence, only from steps with a record. */
export function outcomesHeadline(d: TopicOutcomesResponse | undefined, topic: string, label: string): string {
  if (!d) return `What happened after ${topic} came up.`
  const s = d.steps
  const where = label === 'National' ? 'Across America' : `In ${label}`
  if (!s.meetings.count) return `${where}, no recorded meetings on ${topic} yet.`
  const then: string[] = []
  if (s.actions.count) then.push(`local bodies voted or put it off in ${fmt(s.actions.count)}`)
  if (s.linked_bills.count) then.push(`${fmt(s.linked_bills.count)} named a state bill`)
  const tail = then.length ? `; ${then.join(' and ')}` : ''
  return `${where}, ${topic} came up in ${plural(s.meetings.count, 'meeting', 'meetings')}${tail}.`
}

/** The story screen a step opens, when the story has one. */
export function stepScreen(id: ChainStepId, dataCenterStory: boolean): string | null {
  if (dataCenterStory) {
    return ({ meetings: 'meetings', public: 'voices', actions: 'decisions', bills: 'upcoming', linked_bills: null, next: 'upcoming' } as const)[id]
  }
  return ({ meetings: 'timeline', public: 'positions', actions: 'actions', bills: 'bills', linked_bills: null, next: 'upcoming' } as const)[id]
}
