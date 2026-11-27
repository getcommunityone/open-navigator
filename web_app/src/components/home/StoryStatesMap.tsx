import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
// The state's story plays its drill-down transition on arrival, from the national layout (#1195).
import { DRILL_FROM_NATIONAL } from '../stance/drillState'
import { useQuery } from '@tanstack/react-query'
import { NATIONAL_BBOX, STATES_ALBERS_TOPO, dotsFor, fetchTopo, meetingColor, toFeats, type Feat } from '../../lib/dotMatrix'
import { excerptAroundMark } from '../../lib/highlight'
import QuoteCard from '../stance/QuoteCard'
import { resolveVideoId, startFromUrl } from '../stance/quoteCardUtils'
import {
  BOX_COLORS,
  DISAGREEMENT_LABEL,
  DISAGREEMENT_STROKE,
  PUBLIC_AGAINST_COLOR,
  PUBLIC_AGAINST_LABEL,
  STANCE_LABEL,
  hasDisagreement,
  leanFill,
  leanLine,
  type LeanCounts,
} from './storyColors'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { HOUSE_THEME } from '../../utils/houseTheme'
import { isTouchOnly } from '../../utils/touchOnly'
import { isCurrentPage } from '../../utils/currentPage'
import { useMapKeyboard, westToEast } from '../../hooks/useMapKeyboard'
import { STANCE_ORDER, bandSides, speakersOf, stanceCount, type Stance, type StanceCounts } from '../../utils/boxSplit'
import { missingLegend, SPLIT_NOTE, type TopicPositions } from '../../utils/topicPositions'

export interface StateMarker {
  state_code: string
  state?: string | null
  meetings: number
}

/** One state's real speaker counts (positions `by_state`, #1087), plus Jev's public-against / disagreement meeting
 *  counts (#1117; 0 or missing when none). */
export interface StateStance extends StanceCounts, LeanCounts {
  state_code: string
  /** Meetings for the state in the speaker mart (0 for a state that is here only for its AI reading). */
  meetings?: number
  /** Topic stories (#1200): meetings the AI read where the public didn't speak on the topic (missing, never split). */
  silent_meetings?: number
}

/** One real meeting passage for a state's card: verbatim, with where and when it was said. */
export interface StateQuote {
  place: string
  /** A speaker's recorded side, when the quote is a speaker's own words (#995); absent for a meeting passage. */
  side?: 'for' | 'against' | 'question' | null
  /** The speaker's name as served ("Rob D."), when one was heard. */
  speakerName?: string | null
  /** The speaker's role on record ("Resident"), when given. */
  role?: string | null
  /** The item the comment is on (decision headline), when given. */
  item?: string | null
  /** Verbatim transcript excerpt; matched words in <mark>. */
  text: string
  date: string | null
  /** The meeting's title, for a meeting passage. */
  meeting: string | null
  /** Where the public stood at this meeting, as a short line (#1230); none → no line. */
  stanceNote?: string | null
  /** The recording at the passage's moment, or the recording. */
  url: string | null
  /** The recording's YouTube id, when known (else derived from `url`). */
  videoId?: string | null
  /** Seconds into the recording where the passage starts. */
  startSeconds?: number | null
  /** The meeting's AI summary from the record (#1124), for a meeting passage. */
  summary?: string | null
  /** The meeting page in the app with the scope in its query (#1124); none → no link. */
  analysisUrl?: string | null
}

interface Props {
  /** Real meetings per state (meeting-mentions `counts.by_state`); null while loading. */
  byState: StateMarker[] | null | undefined
  /** Each state's real passages, by state code (speakers' own words first, then meeting passages). Its boxes cycle through
   *  them; a state without one has no card. */
  quotes?: Map<string, StateQuote[]>
  /** Real speaker counts per state, national (#1087). Absent (the rentals story): boxes show meetings only. */
  stance?: StateStance[] | null
  /** The state the page is scoped to: its boxes at full strength, the rest muted. */
  highlight?: string | null
  /** Where a state's boxes go: the story for that state. */
  href: (stateCode: string) => string
  /** What came up, for the captions ("a data center", "short-term rentals"); the data center story by default (#1013). */
  subject?: string
  /** What `stance` counts (#1127): speakers on record (data centers, the default) or meetings as the AI read them
   *  (`topic_meeting_lean`, the other topic stories). Only the words change; the colours and bands are the same. */
  stanceUnit?: StanceUnit
  /** The topic's own position words (#1200, utils/topicPositions) for an AI-read meeting split: legend, hover line and
   *  table headers say "Want limits on short-term rentals" instead of "Public mostly opposed". */
  positions?: TopicPositions
}

export type StanceUnit = 'speakers' | 'meetings'

const fmt = (n: number) => n.toLocaleString('en-US')
const plural = (n: number, one: string, many: string) => `${fmt(n)} ${n === 1 ? one : many}`
const W = NATIONAL_BBOX[2]
const H = NATIONAL_BBOX[3]
const COLS = 80

export { BOX_COLORS, STANCE_LABEL, PUBLIC_AGAINST_COLOR, PUBLIC_AGAINST_LABEL, DISAGREEMENT_LABEL, DISAGREEMENT_STROKE }
/** States with meetings but no stance on record, light to dark by their real meeting count (#1103). */
export const MEETING_GREYS = ['#D2D8DA', '#B3BCC0', '#8F9A9F', '#6B777D'] as const

/** An SVG path for a state's outline (albers coordinates, as drawn by us-atlas). */
export function featPath(f: Feat): string {
  return f.polys
    .map((rings) => rings.map((ring) => 'M' + ring.map(([x, y]) => `${x!.toFixed(1)},${y!.toFixed(1)}`).join('L') + 'Z').join(''))
    .join('')
}

/** Without stance data (the rentals story) a state with meetings is one teal. */
const MEETINGS_ONLY = HOUSE_THEME.seg[0]!

/** The legend's four entries (#1110): three stance colours plus grey. A question is drawn as No side. */
export const LEGEND_STANCES = ['against', 'for', 'neutral'] as const
export const LEGEND_LABEL: Record<(typeof LEGEND_STANCES)[number], string> = {
  against: 'Spoke against',
  for: 'Spoke for',
  neutral: 'No side',
}
/** The same four entries when the split counts meetings by the AI reading (#1127). */
export const AI_LEGEND_LABEL: Record<(typeof LEGEND_STANCES)[number], string> = {
  against: 'Public mostly opposed',
  for: 'Public mostly supported',
  neutral: 'Public split',
}
/** Column and line words for an AI-read meeting split; a meeting reading has no "asked a question". */
const AI_STANCE_LABEL: Record<Stance, string> = {
  against: 'Public mostly opposed',
  for: 'Public mostly supported',
  question: 'Asked a question',
  neutral: 'Public split',
}
const AI_LINE_WORD: Record<Stance, string> = {
  against: 'mostly opposed',
  for: 'mostly supported',
  question: 'asked a question',
  neutral: 'split',
}

/** The real speaker counts as one line ("3 spoke against · 1 asked a question"), or null with none on record. With
 *  `unit` 'meetings' the counts are meetings as the AI read them: "AI reading of 4 meetings: 3 mostly opposed · 1 mostly supported". */
export function stanceLine(s: StanceCounts | undefined, unit: StanceUnit = 'speakers'): string | null {
  if (!s || speakersOf(s) === 0) return null
  const keys = STANCE_ORDER.filter((k) => stanceCount(s, k) > 0)
  if (unit === 'meetings') {
    const total = speakersOf(s)
    const parts = keys.map((k) => `${fmt(stanceCount(s, k))} ${AI_LINE_WORD[k]}`)
    return `AI reading of ${plural(total, 'meeting', 'meetings')}: ${parts.join(' · ')}`
  }
  return keys.map((k) => `${fmt(stanceCount(s, k))} ${STANCE_LABEL[k].toLowerCase()}`).join(' · ')
}

/**
 * A state's AI reading in the topic's words (#1200): "AI reading of 45 meetings where the public spoke: 30 against the
 * cameras · 6 for the cameras · 9 split; in 180 more it didn't speak on it". Zero clauses are left out; null with no reading.
 */
export function positionLine(s: StateStance | undefined, words: TopicPositions): string | null {
  const spoke = s ? speakersOf(s) : 0
  const silent = Math.max(0, s?.silent_meetings ?? 0)
  if (spoke === 0 && silent === 0) return null
  const label: Record<Stance, string> = { against: words.against, for: words.for, question: words.split, neutral: words.split }
  const parts = STANCE_ORDER.filter((k) => k !== 'question' && stanceCount(s!, k) > 0).map((k) => `${fmt(stanceCount(s!, k))} ${label[k].toLowerCase()}`)
  const head = spoke > 0 ? `AI reading of ${plural(spoke, 'meeting', 'meetings')} where the public spoke: ${parts.join(' · ')}` : ''
  const silentMeetings = silent === 1 ? 'meeting' : 'meetings'
  const tail =
    silent > 0
      ? spoke > 0
        ? `in ${fmt(silent)} more ${silentMeetings} the public didn't speak on it`
        : `AI reading: in ${fmt(silent)} ${silentMeetings} the public didn't speak on it`
      : ''
  return [head, tail].filter(Boolean).join('; ')
}

interface Box {
  x: number
  y: number
  code: string | null
  /** Index among its state's boxes, sorted left to right. */
  rank: number
  side: Stance | null
  /** Index among its state's boxes in the same side's band. */
  bandRank: number
}

/**
 * The home page's story map (#985, #995, #1087): the country as a grid of small square boxes in each state's shape (the
 * Explore map's geometry). Where speakers are on record, a state's boxes are split in bands by the real counts of those who
 * spoke against, for, asked a question or took no side; a state with meetings but no speaker on record is one grey; a state
 * with none is the empty tint. Hovering (tapping, on a phone) a box shows one of that state's real passages, cycling through
 * them across its boxes; clicking opens that state's story. Nothing is drawn from a guess: no counts, no split.
 */
export default function StoryStatesMap({ byState, quotes, stance, highlight, href, subject = 'a data center', stanceUnit = 'speakers', positions }: Props) {
  const byMeetings = stanceUnit === 'meetings'
  // Topic words (#1200) only for an AI-read meeting split; the speaker map keeps its own words.
  const words = byMeetings ? positions : undefined
  const lineOf = (st: StateStance | undefined) => (words ? positionLine(st, words) : stanceLine(st, stanceUnit))
  const navigate = useNavigate()
  const location = useLocation()
  const [hover, setHover] = useState<number | null>(null)
  const touch = isTouchOnly()
  const { data: topo, isError } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const grid = useMemo(() => {
    if (!topo) return null
    const feats = toFeats(topo, 'states').filter((f) => f.id !== '72')
    const { dots, step } = dotsFor(feats, NATIONAL_BBOX, COLS)
    // A state too small for a grid point (DC, at this grid) still gets one box, at its centre.
    const seen = new Set(dots.map((d) => d.id))
    for (const f of feats) {
      if (!seen.has(f.id)) dots.push({ x: (f.bbox[0] + f.bbox[2]) / 2, y: (f.bbox[1] + f.bbox[3]) / 2, id: f.id })
    }
    return { feats, dots, step }
  }, [topo])

  const stanceBy = useMemo(() => new Map((stance ?? []).map((s) => [s.state_code, s])), [stance])
  const boxes = useMemo<Box[] | null>(() => {
    if (!grid) return null
    const byFips = new Map<string, typeof grid.dots>()
    for (const d of grid.dots) {
      const list = byFips.get(d.id)
      if (list) list.push(d)
      else byFips.set(d.id, [d])
    }
    const out: Box[] = []
    for (const [fips, ds] of byFips) {
      const code = STATE_FIPS_TO_CODE[fips] ?? null
      // Left to right, then top to bottom, so each side fills one contiguous band of the state.
      const sorted = [...ds].sort((a, b) => a.x - b.x || a.y - b.y)
      const sides = bandSides(code ? stanceBy.get(code) : undefined, sorted.length)
      const seen: Partial<Record<Stance, number>> = {}
      sorted.forEach((d, rank) => {
        const side = sides[rank] ?? null
        const bandRank = side ? (seen[side] = (seen[side] ?? -1) + 1) : rank
        out.push({ x: d.x, y: d.y, code, rank, side, bandRank })
      })
    }
    return out
  }, [grid, stanceBy])
  // Keyboard (#1146): one tab stop, the arrows move state to state west to east; each state shows its first box's card.
  const firstBox = useMemo(() => {
    const m = new Map<string, number>()
    boxes?.forEach((b, i) => {
      if (b.code && b.rank === 0) m.set(b.code, i)
    })
    return m
  }, [boxes])
  const order = useMemo(() => (boxes ? westToEast(boxes, (i) => boxes[i]!.code) : []), [boxes])
  const keyNav = useMapKeyboard<string>({
    keys: order,
    active: hover != null ? boxes?.[hover]?.code ?? null : null,
    setActive: (code) => setHover(code ? firstBox.get(code) ?? null : null),
    initial: highlight,
    noun: 'state',
    describe: (code) => {
      const n = byState?.find((s) => s.state_code === code)
      const st = lineOf(stanceBy.get(code))
      return `${n?.state ?? STATE_CODE_TO_NAME[code] ?? code}: ${plural(n?.meetings ?? 0, 'meeting', 'meetings')}${st ? `; ${st}` : ''}.`
    },
    onActivate: (code) => {
      if (!isCurrentPage(href(code), location.pathname, location.search)) navigate(href(code), { state: DRILL_FROM_NATIONAL })
    },
  })

  if (isError) return <p className="text-sm text-stone-500">The map could not be loaded.</p>
  if (!grid || !boxes || byState == null) return <p className="text-sm text-stone-500" role="status">Loading the map…</p>

  const meetings = new Map(byState.map((s) => [s.state_code, s.meetings]))
  const maxMeetings = Math.max(0, ...byState.map((s) => s.meetings))
  const hasStance = stance != null
  const split = (stance ?? []).filter((s) => speakersOf(s) > 0)
  const speakersTotal = split.reduce((n, s) => n + speakersOf(s), 0)
  const silentTotal = (stance ?? []).reduce((n, s) => n + Math.max(0, s.silent_meetings ?? 0), 0)
  const stateName = (code: string) => byState.find((s) => s.state_code === code)?.state ?? STATE_CODE_TO_NAME[code] ?? code
  const colorOf = (b: Box): string => {
    if (!b.code) return BOX_COLORS.none
    if (b.side) return BOX_COLORS[b.side]
    const n = meetings.get(b.code) ?? 0
    if (n > 0) return hasStance ? leanFill(stanceBy.get(b.code), meetingColor(n, maxMeetings, MEETING_GREYS, BOX_COLORS.meetings)) : MEETINGS_ONLY
    return BOX_COLORS.none
  }

  const listed = [...new Set([...byState.filter((s) => s.meetings > 0).map((s) => s.state_code), ...split.map((s) => s.state_code)])]
    .map((code) => ({ code, name: stateName(code), meetings: meetings.get(code) ?? 0, st: stanceBy.get(code) }))
    .sort((a, b) => speakersOf(b.st) - speakersOf(a.st) || b.meetings - a.meetings || a.name.localeCompare(b.name))
  const withMeetings = byState.filter((s) => s.meetings > 0).length
  // #1117: Jev's reading, only where it is served (public against at P >= 0.7; the refined disagreement rule).
  const leanStates = byMeetings ? [] : (stance ?? []).filter((s) => (s.public_against_meetings ?? 0) > 0 && speakersOf(s) === 0)
  const disagreeStates = (stance ?? []).filter((s) => hasDisagreement(s))
  const hasLean = hasStance && (leanStates.length > 0 || disagreeStates.length > 0)
  const tableStances = byMeetings ? STANCE_ORDER.filter((k) => k !== 'question') : STANCE_ORDER

  const shown = hover != null ? boxes[hover] : undefined
  const shownCode = shown?.code ?? null
  // The card: one of the state's passages, cycling across its boxes (box index mod passages). A box in a side's band shows
  // that side's own words when the state has some; otherwise the state's passages in turn.
  let quote: StateQuote | undefined
  if (shown && shownCode) {
    const all = quotes?.get(shownCode) ?? []
    // A named speaker's own words ("Rob D.") first, wherever the state has some; passages with no one named after.
    const named = all.filter((q) => q.speakerName)
    const own = shown.side ? (named.some((q) => q.side === shown.side) ? named : all).filter((q) => q.side === shown.side) : []
    const pool = named.length ? named : all
    if (own.length) quote = own[shown.bandRank % own.length]
    else if (pool.length) quote = pool[shown.rank % pool.length]
  }
  const shownStance = shownCode ? lineOf(stanceBy.get(shownCode)) : null
  // The card's state is the page the reader is on: no button to it, and the caption says so.
  const shownIsHere = shownCode ? isCurrentPage(href(shownCode), location.pathname, location.search) : false
  // The words for a state with meetings and no reading: the topic's "No AI reading yet" (#1200).
  const noReading = words ? words.unread.charAt(0).toLowerCase() + words.unread.slice(1) : 'no AI reading yet'
  const shownMeetings = shownCode ? meetings.get(shownCode) ?? 0 : 0
  const shownLean = shownCode && hasStance ? leanLine(stanceBy.get(shownCode)) : null
  const left = shown ? (shown.x / W) * 100 : 0
  const size = grid.step * 0.8
  const pad = 4

  const summary =
    `Map of the United States drawn as small boxes in each state's shape. ${plural(withMeetings, 'state has', 'states have')} at least one meeting where ${subject} came up.` +
    (hasStance && split.length
      ? ` In ${plural(split.length, 'state', 'states')} the boxes are split by ${byMeetings ? `an AI reading of ${plural(speakersTotal, 'meeting', 'meetings')}` : `${plural(speakersTotal, 'speaker', 'speakers')} on record`}: ` +
        split.map((s) => `${stateName(s.state_code)}, ${lineOf(s)}`).join('; ') +
        '.'
      : '') +
    (leanStates.length
      ? ` In ${plural(leanStates.length, 'other state', 'other states')} an AI reading of the meetings found the public mostly opposed: ${leanStates.map((s) => stateName(s.state_code)).join(', ')}.`
      : '') +
    (disagreeStates.length
      ? ` In ${plural(disagreeStates.length, 'state', 'states')} the AI reading found officials sided against the public (see the data table): ${disagreeStates.map((s) => stateName(s.state_code)).join(', ')}.`
      : '') +
    ' The data table below lists every state; its links open each state’s story.'

  const onBox = (i: number) => {
    const b = boxes[i]
    if (!b?.code) return
    // On a phone (no hover) the first tap on a state with a card shows that state's card, whose "Open the … story" button
    // is the way in (#1187); before, the tap navigated at once while the card still showed the page's own state, so its
    // button led nowhere. A state with no card, or a second tap on the state shown, opens the story directly (#1120).
    if (touch && b.code !== shownCode && (quotes?.get(b.code)?.length ?? 0) > 0) {
      setHover(i)
      return
    }
    setHover(i)
    if (isCurrentPage(href(b.code), location.pathname, location.search)) return
    navigate(href(b.code), { state: DRILL_FROM_NATIONAL })
  }

  return (
    <div style={{ position: 'relative' }} onMouseLeave={() => setHover(null)} {...keyNav.stageProps}>
      {keyNav.sr}
      <svg viewBox={`${-pad} ${-pad} ${W + pad * 2} ${H + pad * 2}`} className="block h-auto w-full" aria-label={summary} {...keyNav.svgProps}>
        {boxes.map((b, i) => {
          const muted = shownCode ? b.code !== shownCode : !!highlight && b.code !== highlight
          const on = (meetings.get(b.code ?? '') ?? 0) > 0 || !!b.side
          const s = on ? size : size * 0.6
          return (
            <rect
              key={i}
              x={b.x - s / 2}
              y={b.y - s / 2}
              width={s}
              height={s}
              rx={s * 0.12}
              fill={colorOf(b)}
              opacity={muted ? 0.7 : 1}
              stroke={i === hover ? '#1c1917' : undefined}
              strokeWidth={i === hover ? 1.5 : undefined}
              style={{ cursor: b.code ? 'pointer' : 'default' }}
              onMouseEnter={touch ? undefined : () => setHover(i)}
              onClick={() => onBox(i)}
            />
          )
        })}
        {/* State outlines over the boxes (#1103), so neighbouring states read as separate shapes. */}
        <g fill="none" stroke="#57534e" strokeOpacity={0.55} strokeWidth={0.8} strokeLinejoin="round" pointerEvents="none">
          {grid.feats.map((f) => (
            <path key={f.id} d={featPath(f)} />
          ))}
        </g>
      </svg>

      {shown && shownCode && quote && (
        // At the top of the map, on the side away from the box, so it never covers the box it describes.
        <QuoteCard
          className="home-map-card"
          style={{ ...(left < 55 ? { right: 0, top: '2%' } : { left: 0, top: '2%' }), padding: 0, overflow: 'hidden' }}
          place={quote.place}
          date={quote.date}
          quote={excerptAroundMark(quote.text)}
          side={quote.side}
          speakerName={quote.speakerName}
          role={quote.role}
          item={quote.item}
          meeting={quote.meeting}
          stanceNote={quote.stanceNote ?? null}
          videoId={resolveVideoId(quote.videoId, quote.url)}
          startSeconds={quote.startSeconds ?? startFromUrl(quote.url)}
          url={quote.url}
          summary={quote.summary ?? null}
          analysisUrl={quote.analysisUrl ?? null}
        >
          <p style={{ margin: '10px 0 0', paddingTop: 8, borderTop: '1px solid #e7e5e4', fontSize: 12, color: '#57534e' }}>
            {stateName(shownCode)}: {plural(shownMeetings, 'meeting', 'meetings')}
            {shownStance ? ` · ${shownStance}` : hasStance ? (byMeetings ? ` · ${noReading}` : ' · no stance on record') : ''}
          </p>
          {shownLean && <p style={{ margin: '4px 0 0', fontSize: 12, color: '#57534e' }}>{shownLean}</p>}
          {/* A real button, not a caption (#1187): the way into the state's story, on desktop and phones alike. Inline
              styles so it looks the same on the home page and on topic stories (outside .v9). */}
          {shownIsHere ? (
            // Already on this state's story: a link here would do nothing, so the card says where the reader is.
            <p className="home-map-card-here" style={{ margin: '12px 0 0', fontSize: 14, fontWeight: 600, color: '#115e59', textAlign: 'center' }}>
              You’re reading the {stateName(shownCode)} story
            </p>
          ) : (
            <Link
              to={href(shownCode)}
              state={DRILL_FROM_NATIONAL}
              className="home-map-card-open"
              style={{
                display: 'block',
                margin: '12px 0 0',
                padding: '12px 16px',
                minHeight: 44,
                boxSizing: 'border-box',
                borderRadius: 999,
                background: '#0f766e',
                color: '#fff',
                fontSize: 15,
                fontWeight: 700,
                lineHeight: 1.3,
                textAlign: 'center',
                textDecoration: 'none',
              }}
            >
              Open the {stateName(shownCode)} story <span aria-hidden="true">→</span>
            </Link>
          )}
        </QuoteCard>
      )}

      {/* Not a live region: it changes on every pointer move. Keyboard and screen readers use the data table. */}
      <p className="mt-1 min-h-[2.1rem] text-xs leading-snug text-stone-600" aria-live="off">
        {shown && shownCode
          ? `${stateName(shownCode)}: ${plural(shownMeetings, 'meeting', 'meetings')} where ${subject} came up${shownStance ? `; ${shownStance}` : hasStance ? (byMeetings ? `; ${noReading}` : '; no stance on record') : ''}.${shownLean ? ` ${shownLean}` : ''} ${shownIsHere ? 'You’re reading its story.' : touch ? (quote ? 'Tap the button to open its story.' : 'Tap to open its story.') : 'Click to open its story.'}`
          : `${plural(withMeetings, 'state', 'states')} with at least one meeting where ${subject} came up. ${touch ? 'Tap a state to read what was said, then open its story.' : 'Hover a box to read what was said; click to open that state’s story.'}`}
      </p>

      <ul className="mt-0.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] leading-tight text-stone-600" aria-label="Legend" style={{ listStyle: 'none', padding: 0 }}>
        {hasStance &&
          split.length > 0 &&
          LEGEND_STANCES.map((k) => (
            <li key={k} className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: BOX_COLORS[k], display: 'inline-block' }} />
              {words ? (k === 'neutral' ? words.split : words[k]) : (byMeetings ? AI_LEGEND_LABEL : LEGEND_LABEL)[k]}
            </li>
          ))}
        {hasLean && leanStates.length > 0 && (
          <li className="inline-flex items-center gap-1">
            <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: PUBLIC_AGAINST_COLOR, display: 'inline-block' }} />
            {PUBLIC_AGAINST_LABEL}
          </li>
        )}
        <li className="inline-flex items-center gap-1">
          {hasStance ? (
            <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: MEETING_GREYS[2], display: 'inline-block' }} />
          ) : (
            <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: MEETINGS_ONLY, display: 'inline-block' }} />
          )}
          {hasStance
            ? words
              ? `${missingLegend(words)} (darker = more meetings)`
              : byMeetings
              ? 'Meetings, no AI reading yet (darker = more meetings)'
              : 'Meetings, no stance on record (darker = more meetings)'
            : `Meetings where ${subject} came up`}
        </li>
      </ul>
      {/* Compact under the map (#1187) so the first screen keeps room for Browse topics: the method note sits with the
          data table; the legend above still names the AI reading. */}
      <details className="mt-1 text-xs text-stone-700">
        <summary className="cursor-pointer text-stone-600">How to read this map · data table</summary>
        {hasStance && (
          <p className="mt-1 text-xs text-stone-500">
          {byMeetings
            ? split.length > 0
              ? `Split by an AI reading of ${plural(speakersTotal, 'meeting', 'meetings')} in ${plural(split.length, 'state', 'states')}; other states show meetings only.`
              : silentTotal > 0
                ? `In the ${plural(silentTotal, 'meeting', 'meetings')} the AI read, the public didn't speak on it; states show meetings only.`
                : 'No AI reading of these meetings yet; states show meetings only.'
            : split.length > 0
              ? `Split by ${plural(speakersTotal, 'speaker', 'speakers')} on record in ${plural(split.length, 'state', 'states')}; other states show meetings only.`
              : 'No speaker positions on record yet; states show meetings only.'}
          {hasLean || (byMeetings && split.length > 0) ? ' The AI reading is a classifier’s reading of each meeting’s transcript, not counted speakers.' : ''}
          {words ? `${split.length > 0 ? ` ${SPLIT_NOTE}` : ''} Grey: ${missingLegend(words).charAt(0).toLowerCase()}${missingLegend(words).slice(1)}.${words.forMeans ? ` ${words.forMeans}.` : ''}` : ''}
        </p>
        )}

        {listed.length === 0 ? (
          <p className="mt-1 text-stone-500">No meetings on record.</p>
        ) : (
          <div className="mt-1 max-h-64 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th scope="col" className="py-1 pr-2">State</th>
                  <th scope="col" className="py-1 pr-2">Meetings</th>
                  {hasStance &&
                    tableStances.map((k) => (
                      <th key={k} scope="col" className="py-1 pr-2">
                        {words ? (k === 'neutral' || k === 'question' ? words.split : words[k]) : (byMeetings ? AI_STANCE_LABEL : STANCE_LABEL)[k]}
                      </th>
                    ))}
                  {hasStance && words && <th scope="col" className="py-1 pr-2">{words.silent}</th>}
                  {hasLean && (
                    <>
                      {!byMeetings && <th scope="col" className="py-1 pr-2">AI: public mostly opposed</th>}
                      <th scope="col" className="py-1 pr-2">AI: officials sided against the public</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {listed.map((r) => (
                  <tr key={r.code} className="border-t border-stone-200">
                    <td className="py-1 pr-2">
                      <Link to={href(r.code)} state={DRILL_FROM_NATIONAL} className="text-teal-800 underline">
                        {r.name}
                      </Link>
                    </td>
                    <td className="py-1 pr-2">{fmt(r.meetings)}</td>
                    {hasStance &&
                      tableStances.map((k) => (
                        <td key={k} className="py-1 pr-2">
                          {r.st && (speakersOf(r.st) > 0 || (r.st.meetings ?? 1) > 0) ? fmt(stanceCount(r.st, k)) : '—'}
                        </td>
                      ))}
                    {hasStance && words && <td className="py-1 pr-2">{r.st ? fmt(Math.max(0, r.st.silent_meetings ?? 0)) : '—'}</td>}
                    {hasLean && (
                      <>
                        {!byMeetings && <td className="py-1 pr-2">{fmt(r.st?.public_against_meetings ?? 0)}</td>}
                        <td className="py-1 pr-2">{fmt(r.st?.disagreement_meetings ?? 0)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </div>
  )
}
