import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchTrendEvidence,
  fetchTrendingTerms,
  type TrendEvidenceResponse,
  type TrendTerm,
  type TrendTermsResponse,
} from '../../api/trendingTerms'
import { highlightSnippet } from '../../lib/highlight'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import {
  chipAriaLabel,
  clockLabel,
  momentUrl,
  riseLabel,
  trendScopeLabel,
  type TrendChipSort,
} from '../../utils/trendingTerms'

const PAGE = 5

interface Props {
  /** Active place scope from the URL (?state=); terms are counted per state. */
  stateCode?: string
  /** ?city=, carried for the label: the row answers for the state and says so. */
  city?: string
  sort: TrendChipSort
  onSortChange: (s: TrendChipSort) => void
}

/**
 * "Trending in meetings" (#1399): chips of terms rising in meeting speech or over-represented in heated public comment,
 * free and deterministic from our transcripts. Tapping a chip opens the meetings and verbatim quotes that use it, the
 * term highlighted, the speaker as "First L." or "not identified". Horizontal scroll on phones.
 */
export default function TrendingTermsRow({ stateCode, city, sort, onSortChange }: Props) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)

  const q = useQuery<TrendTermsResponse>({
    queryKey: ['trending-terms', stateCode ?? '', city ?? '', sort],
    queryFn: () => fetchTrendingTerms(stateCode, sort, 20, city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const d = q.data
  const scopeState = d ? d.scope.state_code : (stateCode ?? null)
  const stateName = scopeState ? (STATE_CODE_TO_NAME[scopeState] ?? scopeState) : null
  // A city in the URL is answered for its state: say so from the URL itself, so the note never depends on the response.
  const label = trendScopeLabel(stateName, scopeState ? (city ?? d?.scope.requested_city ?? null) : null)
  const open = d?.terms.find((t) => t.term_id === openId) ?? null

  const toggle = (t: TrendTerm) => {
    setOffset(0)
    setOpenId((cur) => (cur === t.term_id ? null : t.term_id))
  }

  return (
    <section className="sc-block" style={{ marginTop: 16 }} aria-labelledby="trending-terms-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p id="trending-terms-title" className="sc-h" style={{ margin: 0 }}>
          Trending in meetings · {label}
        </p>
        <div className="folio-seg sc-chips" role="group" aria-label="Trending terms sort">
          <button type="button" aria-pressed={sort === 'rising'} onClick={() => onSortChange('rising')}>
            ↑ Rising
          </button>
          <button type="button" aria-pressed={sort === 'hot'} onClick={() => onSortChange('hot')}>
            🔥 Most heated
          </button>
        </div>
      </div>

      {q.isLoading && (
        <p className="sc-note" role="status">
          Loading trending terms…
        </p>
      )}
      {q.isError && <p className="sc-note">Trending terms could not be loaded right now.</p>}
      {d && d.terms.length === 0 && (
        <p className="sc-note">
          No {sort === 'hot' ? 'heated' : 'rising'} terms have enough meetings in {label} yet.
          {scopeState ? ' Try National.' : ''}
        </p>
      )}

      {d && d.terms.length > 0 && (
        <ul
          className="trend-chips"
          data-testid="trending-terms-chips"
          style={{
            display: 'flex',
            gap: 8,
            listStyle: 'none',
            padding: '8px 0 4px',
            margin: 0,
            overflowX: 'auto',
            flexWrap: 'nowrap',
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'thin',
          }}
        >
          {d.terms.map((t) => {
            const rl = riseLabel(t)
            const active = openId === t.term_id
            return (
              <li key={t.term_id} style={{ flex: '0 0 auto' }}>
                <button
                  type="button"
                  onClick={() => toggle(t)}
                  aria-expanded={active}
                  aria-controls="trending-term-evidence"
                  aria-label={chipAriaLabel(t, sort, d.year_a ?? '', d.year_b ?? '')}
                  className={`rounded-full border px-3 py-1 text-sm whitespace-nowrap ${
                    active ? 'border-teal-700 bg-teal-50 font-semibold' : 'border-gray-300 bg-white hover:border-teal-600'
                  }`}
                >
                  <span aria-hidden="true" style={{ color: sort === 'hot' ? '#b45309' : '#0f766e', marginRight: 4 }}>
                    {sort === 'hot' ? '🔥' : '↑'}
                  </span>
                  {t.term}
                  {sort === 'rising' && rl && (
                    <span aria-hidden="true" className="ml-1 text-xs text-gray-600">
                      {rl}
                    </span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {d && (
        <p className="sc-note" style={{ marginTop: 4 }}>
          {sort === 'hot'
            ? 'Terms said far more often by people speaking at heated moments (rated heat 4–5, or at meetings where both sides spoke or officials went against the public) than by other public commenters, nationally.'
            : `Share of recorded meetings that say each term, ${d.year_b ?? 'this year'} to date against ${d.year_a ?? 'last year'}.`}{' '}
          Counted from meeting transcripts, no AI. Names of private people are never shown.
        </p>
      )}

      {open && <TermEvidence term={open} stateCode={scopeState ?? undefined} offset={offset} setOffset={setOffset} />}
    </section>
  )
}

function TermEvidence({
  term,
  stateCode,
  offset,
  setOffset,
}: {
  term: TrendTerm
  stateCode?: string
  offset: number
  setOffset: (n: number) => void
}) {
  const q = useQuery<TrendEvidenceResponse>({
    queryKey: ['trending-term-evidence', term.term_id, stateCode ?? '', offset],
    queryFn: () => fetchTrendEvidence(term.term_id, stateCode, offset, PAGE),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const d = q.data
  return (
    <div id="trending-term-evidence" role="region" aria-label={`Meetings that say “${term.term}”`} className="mt-2">
      <p className="sc-h">
        “{term.term}” in {term.n_meetings.toLocaleString('en-US')} meetings
        {d && d.total > 0 ? ` · newest ${Math.min(d.total, offset + PAGE)} of ${d.total} quoted` : ''}
      </p>
      {term.is_sensitive && (
        <p className="sc-note">This term is shown as counts and quotes only; no speaker is named.</p>
      )}
      {q.isLoading && (
        <p className="sc-note" role="status">
          Loading quotes…
        </p>
      )}
      {q.isError && <p className="sc-note">The quotes could not be loaded right now.</p>}
      {d && d.items.length === 0 && <p className="sc-note">No quoted meetings are stored for this term here yet.</p>}
      {d && d.items.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="trending-term-evidence-list">
          {d.items.map((e) => {
            const href = momentUrl(e.video_url, e.start_seconds)
            return (
              <li key={e.video_id} className="border-t border-gray-200 py-2">
                <blockquote className="text-sm" style={{ margin: 0 }}>
                  “{highlightSnippet(e.excerpt)}”
                </blockquote>
                <p className="mt-1 text-xs text-gray-600">
                  {e.speaker_display_name ?? 'Speaker not identified'} · {e.jurisdiction_name ?? 'Unknown place'}
                  {e.state_code ? `, ${e.state_code}` : ''} · {e.meeting_date}
                  {href && (
                    <>
                      {' · '}
                      <a href={href} target="_blank" rel="noreferrer" className="text-primary-700 hover:underline">
                        {e.start_seconds != null ? `Watch at ${clockLabel(e.start_seconds)}` : 'Watch'}
                      </a>
                    </>
                  )}
                </p>
              </li>
            )
          })}
        </ul>
      )}
      {d && d.total > PAGE && (
        <div className="mt-1 flex gap-3 text-sm">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            ← Newer
          </button>
          <button type="button" disabled={offset + PAGE >= d.total} onClick={() => setOffset(offset + PAGE)}>
            Older →
          </button>
        </div>
      )}
    </div>
  )
}
