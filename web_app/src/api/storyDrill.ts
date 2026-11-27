// The records behind each "Who spoke up" number on the data center story (#1288). Types are generated from the FastAPI
// schema (`npm run gen:api`), so the drill-down and the API can't drift apart.
import type { components } from '../lib/api.types'
import api from '../lib/api'
import { withSpan } from '../instrumentation'

type Schemas = components['schemas']

export type DrillSpeaker = Schemas['Speaker']
export type DrillSpeakersResponse = Schemas['SpeakersResponse']
export type DrillVoteDecision = Schemas['VoteDecision']
export type DrillVoteDecisionsResponse = Schemas['VoteDecisionsResponse']
export type DrillCaptionComment = Schemas['CaptionComment']
export type DrillCaptionCommentsResponse = Schemas['CaptionCommentsResponse']

/** Which number was tapped. Each kind has exactly one endpoint whose total is that number. */
export type DrillKind =
  | { kind: 'speakers'; side: 'for' | 'against' | 'question' }
  | { kind: 'votes'; side: 'for' | 'against' }
  | { kind: 'comments'; filter: 'all' }
  | { kind: 'comments'; filter: 'ai' }
  | { kind: 'comments'; filter: 'company'; company: string }

export interface DrillScope {
  stateCode?: string
  city?: string | null
  year?: number
}

export type DrillPage =
  | { kind: 'speakers'; total: number | null; items: DrillSpeaker[]; available: boolean }
  | { kind: 'votes'; total: number | null; totalDecisions: number | null; items: DrillVoteDecision[]; available: boolean }
  | { kind: 'comments'; total: number | null; items: DrillCaptionComment[]; available: boolean; note: string }

export const DRILL_PAGE_SIZE = 25

function scopeParams(scope: DrillScope): Record<string, string> {
  const q: Record<string, string> = {}
  if (scope.stateCode) q.state = scope.stateCode
  if (scope.city) q.city = scope.city
  return q
}

/** A stable key for react-query: the tapped number and the scope it is for. */
export function drillKey(d: DrillKind, scope: DrillScope): (string | number)[] {
  const what = d.kind === 'comments' ? `comments:${d.filter}:${d.filter === 'company' ? d.company : ''}` : `${d.kind}:${d.side}`
  return ['story-drill', what, scope.stateCode ?? 'national', scope.city ?? '', scope.year ?? 2026]
}

/** One page of the records behind the number, newest first. */
export async function fetchDrillPage(d: DrillKind, scope: DrillScope, offset: number, limit = DRILL_PAGE_SIZE): Promise<DrillPage> {
  const q: Record<string, string> = { ...scopeParams(scope), limit: String(limit), offset: String(offset) }
  return withSpan(
    'story-drill.load',
    async (span) => {
      span.setAttribute('drill.kind', d.kind)
      span.setAttribute('drill.offset', offset)
      if (d.kind === 'speakers') {
        const res = await api.get<DrillSpeakersResponse>('/data-centers/speakers', { params: { ...q, side: d.side } })
        return { kind: 'speakers', total: res.data.total ?? null, items: res.data.items ?? [], available: res.data.available !== false }
      }
      if (d.kind === 'votes') {
        const res = await api.get<DrillVoteDecisionsResponse>('/data-centers/vote-decisions', { params: { ...q, side: d.side } })
        return {
          kind: 'votes',
          total: res.data.total_votes ?? null,
          totalDecisions: res.data.total_decisions ?? null,
          items: res.data.items ?? [],
          available: res.data.available !== false,
        }
      }
      const extra: Record<string, string> = { year: String(scope.year ?? 2026) }
      if (d.filter === 'ai') extra.ai = 'true'
      if (d.filter === 'company') extra.company = d.company
      const res = await api.get<DrillCaptionCommentsResponse>('/data-centers/comments', { params: { ...q, ...extra } })
      return {
        kind: 'comments',
        total: res.data.total ?? null,
        items: res.data.items ?? [],
        available: res.data.available !== false,
        note: res.data.note ?? '',
      }
    },
    { 'drill.scope_level': scope.city ? 'city' : scope.stateCode ? 'state' : 'national' },
  )
}

/** How many rows a page holds (the list length the sheet compares with the tile). */
export const pageRows = (p: DrillPage): number => p.items.length

/** Rows the sheet must list in all: a vote tile counts votes, so its list is decisions (totalDecisions). */
export function rowTotal(p: DrillPage): number | null {
  return p.kind === 'votes' ? p.totalDecisions : p.total
}
