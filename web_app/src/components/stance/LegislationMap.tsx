import ChartFrame, { type LegendItem } from '../chart/ChartFrame'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import { fetchTopicLegislation, fetchTopicStateBills, type TopicLegislationResponse, type TopicStateBillsResponse } from '../../api/topicPolicy'
import { STATES_ALBERS_TOPO, fetchTopo } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import {
  NO_BILL_FILL,
  STATUS_FILL,
  STATUS_LABEL,
  STATUS_ORDER,
  countByCategory,
  countByStatus,
  shadeStates,
  yearSpan,
  type BillFilter,
  type StateShade,
} from '../../utils/topicPolicy'
import './storyCharts.css'

interface Props {
  topic: string
  /** The page's active state scope (?state=), highlighted and opened by default. */
  stateCode?: string
  scopeLabel: string
  subject: string
}

interface StateShape {
  code: string
  name: string
  d: string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toShapes(topo: any): StateShape[] {
  const fc = feature(topo, topo.objects.states) as unknown as { features: { id?: string | number; properties?: { name?: string } }[] }
  const path = geoPath()
  const out: StateShape[] = []
  for (const f of fc.features) {
    const code = STATE_FIPS_TO_CODE[String(f.id ?? '').padStart(2, '0')]
    const d = path(f as never)
    if (code && d) out.push({ code, name: f.properties?.name ?? STATE_CODE_TO_NAME[code] ?? code, d })
  }
  return out
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : null

/**
 * State legislation map (#1274): each state coloured by the furthest any of its bills on the topic got (enacted, passed
 * one chamber, introduced and pending, or failed), from our OpenStates bills (public.topic_legislation_bill). A period
 * and a direction filter recolour the map; a state opens its bill list, each bill linked to its OpenStates page. Every
 * state with a bill is also in the list below the map, so nothing is reachable by colour or pointer alone.
 */
export default function LegislationMap({ topic, stateCode, scopeLabel, subject }: Props) {
  const q = useQuery<TopicLegislationResponse>({
    queryKey: ['topic-legislation', topic],
    queryFn: () => fetchTopicLegislation(topic),
    staleTime: 10 * 60_000,
    retry: 1,
  })
  const topo = useQuery({ queryKey: ['topo', STATES_ALBERS_TOPO], queryFn: () => fetchTopo(STATES_ALBERS_TOPO), staleTime: Infinity })
  const shapes = useMemo(() => (topo.data ? toShapes(topo.data) : []), [topo.data])

  const span = useMemo(() => (q.data ? yearSpan(q.data.summary) : null), [q.data])
  const recentFrom = span ? Math.max(span[0], span[1] - 1) : null
  const [period, setPeriod] = useState<'recent' | 'all'>('recent')
  const [category, setCategory] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)

  const filter: BillFilter = { sinceYear: period === 'recent' ? recentFrom : null, category }
  const shades = useMemo(() => (q.data ? shadeStates(q.data.summary, filter) : []), [q.data, filter.sinceYear, filter.category]) // eslint-disable-line react-hooks/exhaustive-deps
  const catCounts = useMemo(() => (q.data ? countByCategory(q.data.summary, filter.sinceYear) : new Map<string, number>()), [q.data, filter.sinceYear])
  const byCode = useMemo(() => new Map(shades.map((s) => [s.state_code, s])), [shades])
  const counts = countByStatus(shades)
  const billCount = shades.reduce((n, s) => n + s.bills, 0)
  // The page's scoped state opens by default; 'none' means the reader closed it. A new scope resets the choice.
  useEffect(() => setPicked(null), [stateCode])
  const open = picked === 'none' ? null : (picked ?? stateCode ?? null)
  const openShade = open ? byCode.get(open) : undefined
  const hoverShade = hover ? byCode.get(hover) : undefined

  const title = <p className="sc-h">State bills on {subject} · {scopeLabel === 'National' ? 'every state' : `${scopeLabel} highlighted`}</p>

  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading state bills…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">State bills could not be loaded right now.</p>
      </div>
    )
  }
  if (!q.data.available || q.data.total_bills === 0) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">No state bills on {subject} in our OpenStates data yet.</p>
      </div>
    )
  }

  const periodLabel = period === 'recent' && recentFrom && span ? `${recentFrom}–${span[1]}` : span ? `${span[0]}–${span[1]}` : 'all years'
  const cats = q.data.categories.filter((c) => c.bills > 0)
  const toggle = (code: string) => setPicked(open === code ? 'none' : code)
  const describe = (s: StateShade | undefined, code: string) =>
    s
      ? `${s.state ?? STATE_CODE_TO_NAME[code] ?? code}: ${STATUS_LABEL[s.status].toLowerCase()} (${s.bills.toLocaleString('en-US')} bill${s.bills === 1 ? '' : 's'})`
      : `${STATE_CODE_TO_NAME[code] ?? code}: no bill in this view`

  // Title and key (#1409): the takeaway from the real bill counts; the key uses the same fills the states are drawn with.
  const furthest = STATUS_ORDER.find((st) => counts[st] > 0)
  const frameTitle = `${billCount.toLocaleString('en-US')} state bill${billCount === 1 ? '' : 's'} on ${subject} in ${shades.length} state${shades.length === 1 ? '' : 's'}${
    furthest && counts[furthest] > 0 ? `; ${counts[furthest]} ${counts[furthest] === 1 ? 'state' : 'states'} ${STATUS_LABEL[furthest].toLowerCase()}` : ''
  } · ${periodLabel}`
  const legend: LegendItem[] = [
    ...STATUS_ORDER.map((st) => ({ key: st, label: `${STATUS_LABEL[st]} (${counts[st]})`, color: STATUS_FILL[st] })),
    { key: 'none', label: 'No bill in this view', color: NO_BILL_FILL },
  ]

  return (
    <div className="sc-block lm">
      <div className="sc-controls" role="group" aria-label="Which bills">
        <div className="lm-seg" role="group" aria-label="Period">
          {(['recent', 'all'] as const).map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={period === p}
              className="lm-chip"
              onClick={() => setPeriod(p)}
            >
              {p === 'recent' && recentFrom && span ? `${recentFrom}–${span[1]}` : span ? `All years (${span[0]}–${span[1]})` : 'All years'}
            </button>
          ))}
        </div>
        <label className="lm-select">
          <select value={category ?? ''} onChange={(e) => setCategory(e.target.value || null)} aria-label="Direction of the bill">
            <option value="">Every direction</option>
            {cats.map((c) => (
              <option key={c.category} value={c.category}>
                {c.label ?? c.category} ({(catCounts.get(c.category) ?? 0).toLocaleString('en-US')})
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="sc-note" aria-live="polite">
        <b>{billCount.toLocaleString('en-US')}</b> bill{billCount === 1 ? '' : 's'} in <b>{shades.length}</b> state
        {shades.length === 1 ? '' : 's'}, {periodLabel}
        {category ? `, ${(cats.find((c) => c.category === category)?.label ?? category).toLowerCase()}` : ''}.
      </p>

      <ChartFrame title={frameTitle} caption={`State bills on ${subject} by the furthest any bill got`} legend={legend}>
      <div className="lm-mapwrap">
        {topo.isError ? (
          <p className="sc-note">The map shapes could not be loaded; the state list below has every bill.</p>
        ) : (
          <svg viewBox="0 0 975 610" className="sc-svg lm-map" role="group" aria-label={`Map of state bills on ${subject}`}>
            {shapes.map((s) => {
              const shade = byCode.get(s.code)
              const isOpen = open === s.code
              return (
                <path
                  key={s.code}
                  d={s.d}
                  className={`lm-state${isOpen ? ' is-open' : ''}${shade ? ' has-bills' : ''}`}
                  style={{ fill: shade ? STATUS_FILL[shade.status] : NO_BILL_FILL }}
                  tabIndex={shade ? 0 : -1}
                  role={shade ? 'button' : undefined}
                  aria-pressed={shade ? isOpen : undefined}
                  aria-label={describe(shade, s.code)}
                  onMouseEnter={() => setHover(s.code)}
                  onMouseLeave={() => setHover((h) => (h === s.code ? null : h))}
                  onFocus={() => setHover(s.code)}
                  onBlur={() => setHover((h) => (h === s.code ? null : h))}
                  onClick={() => shade && toggle(s.code)}
                  onKeyDown={(e) => {
                    if (shade && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault()
                      toggle(s.code)
                    }
                  }}
                >
                  <title>{describe(shade, s.code)}</title>
                </path>
              )
            })}
          </svg>
        )}
        <p className="lm-readout" aria-hidden="true">
          {hover ? describe(hoverShade, hover) : 'Tap or hover a state.'}
        </p>
      </div>
      </ChartFrame>

      {openShade && (
        <StateBills topic={topic} shade={openShade} filter={filter} cats={q.data.categories} onClose={() => setPicked('none')} />
      )}
      {open && !openShade && (
        <p className="sc-note">{STATE_CODE_TO_NAME[open] ?? open} has no bill on {subject} in this view.</p>
      )}

      <details className="lm-all">
        <summary>Every state with a bill ({shades.length})</summary>
        <ul className="lm-statelist">
          {[...shades]
            .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.state_code.localeCompare(b.state_code))
            .map((s) => (
              <li key={s.state_code}>
                <button type="button" className="lm-statebtn" onClick={() => toggle(s.state_code)} aria-pressed={open === s.state_code}>
                  <span className="lm-swatch" style={{ background: STATUS_FILL[s.status] }} aria-hidden="true" />
                  {s.state ?? STATE_CODE_TO_NAME[s.state_code] ?? s.state_code}
                  <span className="lm-count">
                    {STATUS_LABEL[s.status]} · {s.bills.toLocaleString('en-US')}
                  </span>
                </button>
              </li>
            ))}
        </ul>
      </details>

      <p className="sc-note">
        From our copy of OpenStates: state bills whose subject tags, title or abstract name {subject}. Colour is the
        furthest any bill got, from its own recorded actions. Direction comes from keyword rules on the title and abstract;
        a bill whose text doesn&apos;t say which way is counted as &ldquo;direction not stated&rdquo; and shown by status only.
        Omnibus bills that never name the topic in their title or abstract are missed.
      </p>
    </div>
  )
}

function StateBills({
  topic,
  shade,
  filter,
  cats,
  onClose,
}: {
  topic: string
  shade: StateShade
  filter: BillFilter
  cats: TopicLegislationResponse['categories']
  onClose: () => void
}) {
  const q = useQuery<TopicStateBillsResponse>({
    queryKey: ['topic-state-bills', topic, shade.state_code, filter.sinceYear, filter.category],
    queryFn: () => fetchTopicStateBills(topic, shade.state_code, filter),
    staleTime: 10 * 60_000,
    retry: 1,
  })
  const catLabel = new Map(cats.map((c) => [c.category, c.label ?? c.category]))
  const name = shade.state ?? STATE_CODE_TO_NAME[shade.state_code] ?? shade.state_code
  const bills = q.data?.bills ?? []
  return (
    <div className="sc-detail lm-detail" aria-live="polite">
      <div className="lm-detail-head">
        <p className="sc-detail-title">
          {name}: {shade.bills.toLocaleString('en-US')} bill{shade.bills === 1 ? '' : 's'}
        </p>
        <button type="button" className="lm-chip" onClick={onClose} aria-label={`Close ${name}'s bills`}>
          Close
        </button>
      </div>
      {q.isLoading && <p className="sc-note" role="status">Loading {name}&apos;s bills…</p>}
      {q.isError && <p className="sc-note">{name}&apos;s bills could not be loaded right now.</p>}
      {q.data && q.data.matching > bills.length && (
        <p className="sc-note">
          Showing the first {bills.length.toLocaleString('en-US')} of {q.data.matching.toLocaleString('en-US')}: furthest
          along first, then newest.
        </p>
      )}
      <ul className="lm-bills">
        {bills.map((b) => (
          <li key={b.bill_id}>
            <span
              className="sc-tag"
              style={{
                background: STATUS_FILL[b.status],
                color: b.status === 'enacted' || b.status === 'passed_chamber' ? 'var(--paper)' : 'var(--ink)',
              }}
            >
              {STATUS_LABEL[b.status]}
            </span>{' '}
            <span className="sc-tag lm-cat">{catLabel.get(b.category) ?? b.category}</span>
            <div className="lm-bill-title">
              {b.url ? (
                <a href={b.url} target="_blank" rel="noopener noreferrer">
                  {b.identifier}
                </a>
              ) : (
                b.identifier
              )}
              {b.session ? <span className="lm-meta"> · {b.session} session</span> : null} — {b.title}
            </div>
            {b.last_action && (
              <div className="lm-meta">
                Last action{b.last_action_date ? ` ${fmtDate(b.last_action_date)}` : ''}: {b.last_action}
                {b.status === 'failed' && b.passed_a_chamber ? ' (it had passed one chamber)' : ''}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
