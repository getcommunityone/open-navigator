import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import {
  DRILL_PAGE_SIZE,
  drillKey,
  fetchDrillPage,
  rowTotal,
  type DrillCaptionComment,
  type DrillKind,
  type DrillPage,
  type DrillScope,
  type DrillSpeaker,
  type DrillVoteDecision,
  type DrillDisagreementMeeting,
} from '../../api/storyDrill'
import { hasQuoteText, highlightSnippet } from '../../lib/highlight'
import { useIsMobile } from '../../hooks/useMediaQuery'
import { StanceShapeChip } from './StanceShapeChip'
import { SpeakerName } from './SpeakerName'
import { HeatFlames } from './HeatFlames'
import './KpiDrill.css'

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The number on a KPI tile as a button that opens the records behind it (#1288). The visible text is the number exactly as
 * the tile showed it; only the accessible name adds what tapping does. A tile with no records behind it (0, "not recorded",
 * "—") is never wrapped: the caller passes `drillable={false}` and the number stays plain text.
 */
export function DrillValue({
  children,
  label,
  open,
  controls,
  onToggle,
  drillable = true,
  text = false,
}: {
  children: ReactNode
  /** What the number counts, for screen readers ("spoke against"). */
  label: string
  open: boolean
  controls: string
  onToggle: () => void
  drillable?: boolean
  /** The number sits inside a sentence (an underlined phrase, not a big figure). */
  text?: boolean
}) {
  if (!drillable) return <>{children}</>
  return (
    <button
      type="button"
      className={text ? 'kpi-drill-value-text' : 'kpi-drill-value'}
      aria-expanded={open}
      aria-controls={open ? controls : undefined}
      onClick={onToggle}
      data-drill-open={open ? 'true' : undefined}
      title={open ? 'Hide the records' : 'Show the records behind this number'}
    >
      {children}
      <span className="sr-only">
        {' '}
        {label}: {open ? 'hide' : 'show'} the records
      </span>
    </button>
  )
}

/** "First L." when known: the API serves residents only that way (AGENTS.md, Privacy). */
const who = (name: string | null | undefined) => name || 'Speaker not named'

const place = (j?: string | null, s?: string | null) => [j, s].filter(Boolean).join(', ')

const BASIS: Record<string, string> = {
  data_center_decision: 'Counted because the decision it was on names a data center',
  data_center_item: 'Counted because the agenda item it was on names a data center',
  own_words: 'Counted because the speaker names a data center',
  same_item: 'Counted because another speaker on the same item names a data center',
}

function SpeakerRow({ s }: { s: DrillSpeaker }) {
  const href = s.jump_url ?? s.video_url
  return (
    <li className="kpi-drill-row">
      {hasQuoteText(s.quote_highlighted) || hasQuoteText(s.quote) ? (
        <blockquote className="kpi-drill-quote">“{highlightSnippet(s.quote_highlighted ?? s.quote ?? '')}”</blockquote>
      ) : (
        <p className="kpi-drill-meta">No words were captured for this speaker.</p>
      )}
      <p className="kpi-drill-meta">
        <strong>{who(s.speaker_display_name)}</strong>
        {s.speaker_role ? ` · ${s.speaker_role}` : ''} · {place(s.jurisdiction_name, s.state_code)}
        {s.meeting_date ? ` · ${s.meeting_date}` : ''}
        {href && (
          <>
            {' · '}
            <a href={href} target="_blank" rel="noopener noreferrer">
              {s.jump_url ? 'Watch this moment' : 'Watch the meeting'}
            </a>
          </>
        )}
      </p>
      {(s.decision_headline || (s.match_basis && BASIS[s.match_basis])) && (
        <p className="kpi-drill-meta kpi-drill-basis">
          {s.match_basis && BASIS[s.match_basis] ? BASIS[s.match_basis] : 'On'}
          {s.decision_headline ? `: ${s.decision_headline}` : '.'}
        </p>
      )}
    </li>
  )
}

function VoteRow({ d }: { d: DrillVoteDecision }) {
  return (
    <li className="kpi-drill-row">
      <p className="kpi-drill-title">
        {d.decision_url ? <Link to={d.decision_url}>{d.headline ?? 'Decision'}</Link> : (d.headline ?? 'Decision')}
      </p>
      <p className="kpi-drill-meta">
        <strong>
          {fmt(d.votes_for)} for, {fmt(d.votes_against)} against
        </strong>
        {d.outcome ? ` · ${d.outcome}` : ''} · {place(d.jurisdiction_name, d.state_code)}
        {d.meeting_date ? ` · ${d.meeting_date}` : ''}
        {d.video_url && (
          <>
            {' · '}
            <a href={d.video_url} target="_blank" rel="noopener noreferrer">
              Watch the meeting
            </a>
          </>
        )}
      </p>
    </li>
  )
}

function CommentRow({ c }: { c: DrillCaptionComment }) {
  if (c.possible_minor) {
    return (
      <li className="kpi-drill-row is-withheld">
        <p className="kpi-drill-meta">
          {place(c.jurisdiction_name, c.state_code)}
          {c.meeting_date ? ` · ${c.meeting_date}` : ''}
        </p>
        <p className="kpi-drill-meta">{c.withheld_reason}</p>
      </li>
    )
  }
  const tags = [...(c.concern_keys ?? []), ...(c.company_keys ?? []), ...(c.mentions_ai ? ['AI'] : [])]
  return (
    <li className="kpi-drill-row">
      <p className="kpi-drill-meta">
        <SpeakerName
          name={c.speaker_display_name}
          possibleName={c.possible_name}
          attribution={{
            method: c.attribution_method,
            confidence: c.attribution_confidence,
            tier: c.attribution_tier,
            evidence: c.attribution_evidence,
          }}
        />{' '}
        · {place(c.jurisdiction_name, c.state_code)}
        {c.meeting_date ? ` · ${c.meeting_date}` : ''}
        {c.jump_url && (
          <>
            {' · '}
            <a href={c.jump_url} target="_blank" rel="noopener noreferrer">
              Watch this comment
            </a>
          </>
        )}
      </p>
      <StanceShapeChip shape={c.stance_shape} cue={c.shape_cue_text} />
      {c.heat != null && (
        <p className="kpi-drill-meta">
          <HeatFlames heat={c.heat} method={c.heat_method} />
        </p>
      )}
      {tags.length > 0 && <p className="kpi-drill-meta kpi-drill-basis">Keywords matched: {tags.map((t) => t.replace(/_/g, ' ')).join(', ')}</p>}
    </li>
  )
}

const leanWord = (l: string | null | undefined) =>
  !l ? null : l.replace(/^mostly_/, 'mostly ').replace(/_/g, ' ').replace('supportive', 'for').replace('supported', 'for').replace('opposed', 'against')

/** A meeting where officials sided against the public (#1330): the two readings, the outcome and the recording. */
function DisagreementRow({ m }: { m: DrillDisagreementMeeting }) {
  return (
    <li className="kpi-drill-row">
      <p className="kpi-drill-title">{place(m.jurisdiction_name, m.state_code)}{m.meeting_date ? ` · ${m.meeting_date}` : ''}</p>
      <p className="kpi-drill-meta">
        Public {leanWord(m.public_lean) ?? '—'}; officials {leanWord(m.official_lean) ?? '—'}
        {m.outcome ? ` · outcome: ${m.outcome.replace(/_/g, ' ')}` : ''}
        {m.video_url && (
          <>
            {' · '}
            <a href={m.video_url} target="_blank" rel="noopener noreferrer">
              Watch the meeting
            </a>
          </>
        )}
      </p>
    </li>
  )
}

/** Rows of every loaded page. */
function rowsOf(pages: DrillPage[]): ReactNode[] {
  return pages.flatMap((p) => {
    if (p.kind === 'speakers') return p.items.map((s) => <SpeakerRow key={s.public_comment_id} s={s} />)
    if (p.kind === 'votes') return p.items.map((d) => <VoteRow key={d.data_center_decision_id} d={d} />)
    if (p.kind === 'disagreement') return p.items.map((m) => <DisagreementRow key={m.video_id} m={m} />)
    return p.items.map((c) => <CommentRow key={c.data_center_comment_id} c={c} />)
  })
}

/** The heading's count line, from the API's own total (it equals the tile). */
export function drillSummary(d: DrillKind, first: DrillPage | undefined, scopeLabel: string): string {
  if (!first || first.total == null) return scopeLabel
  const n = first.total
  if (first.kind === 'votes') {
    const decisions = first.totalDecisions ?? 0
    return `${fmt(n)} ${n === 1 ? 'vote' : 'votes'} ${d.kind === 'votes' ? d.side : ''} in ${fmt(decisions)} ${decisions === 1 ? 'decision' : 'decisions'} · ${scopeLabel}`
  }
  if (first.kind === 'speakers') return `${fmt(n)} ${n === 1 ? 'speaker' : 'speakers'} · ${scopeLabel}`
  if (first.kind === 'disagreement') return `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'} · ${scopeLabel}`
  return `${fmt(n)} ${n === 1 ? 'comment' : 'comments'} · ${scopeLabel}`
}

/**
 * The list behind a tapped number (#1288): inline under the tiles on a wide screen, a full-height bottom sheet on a phone
 * (the CSS decides), with a Close button and Escape. Pages of 25 load on "Show more"; the list ends when every record the
 * tile counts is shown, so its length equals the number.
 */
export function KpiDrillSheet({
  id,
  drill,
  title,
  scope,
  scopeLabel,
  onClose,
}: {
  id: string
  drill: DrillKind
  /** What the tapped number counts, as the tile says it ("Spoke against"). */
  title: string
  scope: DrillScope
  /** The scope the list is for, exactly as the story's label says it ("Alabama", "National"). */
  scopeLabel: string
  onClose: () => void
}) {
  const headingId = useId()
  const ref = useRef<HTMLElement>(null)
  // On a phone the list is a bottom sheet over the whole story, so it lives under <body>, outside the screen's transforms.
  const phone = useIsMobile()
  const q = useInfiniteQuery({
    queryKey: drillKey(drill, scope),
    queryFn: ({ pageParam }) => fetchDrillPage(drill, scope, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, all) => {
      const loaded = all.reduce((n, p) => n + p.items.length, 0)
      const total = rowTotal(last)
      return total != null && loaded < total && last.items.length === DRILL_PAGE_SIZE ? loaded : undefined
    },
    staleTime: 5 * 60_000,
  })

  // On a phone the sheet is modal: the story behind it is inert, so Tab stays in the sheet. Declared first so
  // its cleanup runs first and the opener can take focus again.
  useEffect(() => {
    if (!phone) return
    const root = document.getElementById('root')
    if (!root) return
    root.setAttribute('inert', '')
    return () => root.removeAttribute('inert')
  }, [phone])

  // Focus moves into the list (again when it moves into the phone sheet), and back to the number that opened it when
  // the list closes.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    return () => {
      if (opener && opener.isConnected) opener.focus()
    }
  }, [])
  useEffect(() => {
    ref.current?.focus()
  }, [phone])

  // Escape closes this list only when focus is in it (two lists can be open on one screen).
  const onKeyDown = (e: { key: string; stopPropagation: () => void }) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    }
  }

  const pages = q.data?.pages ?? []
  const first = pages[0]
  const loaded = pages.reduce((n, p) => n + p.items.length, 0)
  const total = first ? rowTotal(first) : null
  const body = (
    <>
      {phone && <div className="kpi-drill-scrim" onClick={onClose} aria-hidden="true" />}
      <section
        id={id}
        ref={ref}
        tabIndex={-1}
        className={phone ? 'kpi-drill-sheet is-sheet' : 'kpi-drill-sheet'}
        role={phone ? 'dialog' : 'region'}
        aria-modal={phone ? true : undefined}
        aria-labelledby={headingId}
        data-testid="kpi-drill"
        onKeyDown={onKeyDown}
        data-keeps-escape
        data-lenis-prevent
      >
        <header className="kpi-drill-head">
          <div>
            <h3 id={headingId} className="kpi-drill-h">
              {title}
            </h3>
            <p className="kpi-drill-meta" data-testid="kpi-drill-summary">
              {drillSummary(drill, first, scopeLabel)}
            </p>
          </div>
          <button type="button" className="kpi-drill-close" onClick={onClose} aria-label={`Close the ${title.toLowerCase()} list`}>
            Close
          </button>
        </header>
        {first?.kind === 'comments' && first.note && <p className="kpi-drill-meta kpi-drill-note">{first.note}</p>}
        {q.isLoading ? (
          <p className="kpi-drill-meta" role="status">
            Loading the records…
          </p>
        ) : q.isError ? (
          <p className="kpi-drill-meta">These records couldn&apos;t be loaded. Try again later.</p>
        ) : first && !first.available ? (
          <p className="kpi-drill-meta">These records aren&apos;t loaded in this database yet.</p>
        ) : (
          <>
            <ol className="kpi-drill-list" data-testid="kpi-drill-list" data-total={total ?? undefined}>
              {rowsOf(pages)}
            </ol>
            {q.hasNextPage ? (
              <button type="button" className="kpi-drill-more" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
                {q.isFetchingNextPage ? 'Loading…' : `Show more (${fmt(loaded)} of ${fmt(total ?? 0)})`}
              </button>
            ) : (
              total != null &&
              total > 0 && (
                <p className="kpi-drill-meta kpi-drill-end">
                  All {fmt(total)} shown.
                </p>
              )
            )}
          </>
        )}
      </section>
    </>
  )
  return phone && typeof document !== 'undefined' ? createPortal(body, document.body) : body
}

/** The list behind each "Who spoke up" figure; every figure key has one. */
export function figureDrill(key: 'for' | 'against' | 'question' | 'votes_for' | 'votes_against'): DrillKind {
  if (key === 'votes_for') return { kind: 'votes', side: 'for' }
  if (key === 'votes_against') return { kind: 'votes', side: 'against' }
  return { kind: 'speakers', side: key }
}

/** A number opens a list only when there are records behind it: a count above 0 (never null, "—" or "not recorded"). */
export const isDrillable = (value: number | null | undefined): value is number => value != null && Number.isFinite(value) && value > 0
