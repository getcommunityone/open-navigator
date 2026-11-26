import { useCallback, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchChartData } from '../../api/stance'
import { chartSpec, type DotGroup, type DotsSpec } from '../../utils/stanceGame'
import { docsUrl } from '../../utils/docsLinks'
import { GROUP_COLORS, HOUSE_STYLE } from '../../utils/houseTheme'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { youtubeThumbnail } from '../../lib/youtubeThumbnail'
import MeetingVideoModal, { type MeetingVideo } from './MeetingVideoModal'

interface Props {
  chartKey: string
  round: number
  /** Only the round in view and its neighbours load their data. */
  enabled: boolean
  stateCode: string | undefined
  /** Full state name when a state is chosen, otherwise null (national). */
  stateName: string | null
  /** A city, for the data stories (the challenge never narrows its charts below a state). */
  city?: string | null
  /** What the caption says the figure shows; defaults to the state name or "National". */
  scopeLabel?: string
  /** Shown under "No data available" (for example buttons that broaden the place). */
  emptyExtra?: ReactNode
  /** Draw the dataset another way (`meetings`: the meeting passages' data as one dot per meeting). */
  view?: 'meetings'
}

const fmt = (n: number) => n.toLocaleString('en-US')

/** The dataset behind one round's chart, shared by the chart and the headline through the query cache. */
export function useChartData(chartKey: string, enabled: boolean, stateCode: string | undefined, city?: string | null) {
  const c = stateCode && city ? city : ''
  return useQuery({
    queryKey: ['stance', 'chart', chartKey, stateCode ?? 'national', c],
    queryFn: () => fetchChartData(chartKey, stateCode, c || undefined),
    enabled,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

/** A group's colour: its stance tone (set in stance.css, with a shape of its own) or the next colour of the house theme. */
function dotLook(g: DotGroup, gi: number): { className: string; background: string | undefined } {
  return g.tone ? { className: ` stance-dot--${g.tone}`, background: undefined } : { className: '', background: GROUP_COLORS[gi % GROUP_COLORS.length] }
}

/**
 * One mark per real record (or per stated number of records), grouped under "Group · N records · P%". Roving focus: arrow
 * keys move between the dots. The dots appear one after another when the chart arrives (stance.css reads `--f`).
 * A meeting dot with a YouTube recording (#972) previews its thumbnail in the tooltip and plays in a modal on click, Enter
 * or Space; nothing loads from YouTube before that. Other dots open their source in a new tab as before.
 */
export function Dots({ spec }: { spec: DotsSpec }) {
  const { bind, tip, hide } = useTooltip()
  const [rove, setRove] = useState(0)
  const [playing, setPlaying] = useState<{ video: MeetingVideo; from: number } | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const playingFrom = useRef<number | null>(null)
  const closeVideo = useCallback(() => {
    const from = playingFrom.current
    playingFrom.current = null
    setPlaying(null)
    // Back to the dot the video came from, so keyboard users keep their place.
    if (from != null) requestAnimationFrame(() => root.current?.querySelector<HTMLElement>(`[data-dot="${from}"]`)?.focus())
  }, [])
  const flat = useMemo(() => spec.groups.flatMap((g, gi) => g.dots.map((d) => ({ d, gi, label: g.label }))), [spec])
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
    const to = e.key === 'Home' ? 0 : e.key === 'End' ? flat.length - 1 : step ? Math.min(flat.length - 1, Math.max(0, rove + step)) : null
    if (to == null) return
    e.preventDefault()
    e.stopPropagation()
    setRove(to)
    root.current?.querySelector<HTMLElement>(`[data-dot="${to}"]`)?.focus()
  }
  let n = -1
  const total = flat.length
  return (
    <>
    <div className="stance-dots" ref={root} data-keys-own onKeyDown={onKey}>
      {spec.groups.map((g, gi) => {
        const look = dotLook(g, gi)
        return (
        <div className="stance-dotgroup" key={g.key} data-group={g.key}>
          <p className="stance-dotgroup-head">
            <span className={`stance-swatch${look.className}`} style={{ background: look.background }} aria-hidden="true" />
            {g.heading}
          </p>
          <div className="stance-dotrow" role="list" aria-label={g.heading}>
            {g.dots.map((d) => {
              n += 1
              const i = n
              const sub = [d.place, d.date].filter(Boolean).join(' · ') || undefined
              const info = { cat: g.label, val: d.title, sub, thumb: d.video ? youtubeThumbnail(d.video.videoId, 'mqdefault') ?? undefined : undefined }
              const label = `${d.title}${d.place ? `, ${d.place}` : ''}${d.date ? `, ${d.date}` : ''}${
                d.video ? ' (plays the recording)' : d.url ? ' (opens the source)' : ''
              }`
              const b = bind(info)
              const play = d.video
                ? () => {
                    hide()
                    playingFrom.current = i
                    setPlaying({ video: { ...d.video!, title: d.title, sub, url: d.url, quote: d.quote ?? null }, from: i })
                  }
                : null
              const common = {
                className: `stance-dot${look.className}${d.weight != null && d.weight < spec.perDot ? ' is-part' : ''}`,
                'data-dot': i,
                'aria-label': label,
                tabIndex: i === rove ? 0 : -1,
                style: { background: look.background, ['--f' as string]: total > 1 ? i / total : 0 },
                ...b,
                onFocus: (e: { currentTarget: Element }) => {
                  setRove(i)
                  b.onFocus(e)
                },
                ...(play && {
                  'aria-haspopup': 'dialog' as const,
                  onClick: (e: MouseEvent) => {
                    // A modifier click still opens YouTube in a tab, like any link.
                    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
                    e.preventDefault()
                    play()
                  },
                  onKeyDown: (e: KeyboardEvent) => {
                    if (e.key === ' ') {
                      e.preventDefault()
                      play()
                    }
                  },
                }),
              }
              return d.url ? (
                <a key={d.id + i} role="listitem" href={d.url} target="_blank" rel="noopener noreferrer" {...common} />
              ) : (
                <span key={d.id + i} role="listitem" {...common} />
              )
            })}
          </div>
        </div>
        )
      })}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
      <p className="stance-note stance-hint-keys">Use the arrow keys to move between dots.</p>
      {flat.some((x) => x.d.url) && (
        <p className="stance-note stance-hint-touch">{flat.some((x) => x.d.video) ? 'Tap a dot to play the meeting.' : 'Tap a dot to open it.'}</p>
      )}
    </div>
    {/* Outside the dots' div: React portals bubble events up the React tree, so the dialog's keys must not reach the
        dots' arrow-key handler and move focus behind the dialog. */}
    <MeetingVideoModal video={playing?.video ?? null} onClose={closeVideo} />
    </>
  )
}

/** The chart for one round: one simple figure from the dataset the statement names, its FIG. caption and data table. */
export default function ChartPanel({ chartKey, round, enabled, stateCode, stateName, city, scopeLabel, emptyExtra, view }: Props) {
  const q = useChartData(chartKey, enabled, stateCode, city)
  const spec = useMemo(() => chartSpec(chartKey, q.data, stateName, view), [chartKey, q.data, stateName, view])
  const [open, setOpen] = useState(false)
  const fig = String(round).padStart(2, '0')
  const scope = scopeLabel ?? stateName ?? 'National'
  const hasLinks = Boolean(spec?.groups.some((g) => g.dots.some((d) => d.url)))
  const hasVideos = Boolean(spec?.groups.some((g) => g.dots.some((d) => d.video)))

  return (
    <figure className="stance-figure" aria-label={spec?.title ?? 'Chart'}>
      {q.isLoading && enabled ? (
        <p className="folio-muted" role="status">
          Loading chart…
        </p>
      ) : !spec ? (
        <div className="stance-nodata" role="status">
          <p>{q.isError ? 'This chart could not be loaded right now.' : 'No data available for this chart'}</p>
          {emptyExtra}
        </div>
      ) : (
        <Dots spec={spec} />
      )}
      <figcaption className="folio-fig">
        <b>FIG. {fig}</b> — {spec ? `${spec.title}, ${scope}.` : `${scope}.`}
        {spec && ` ${spec.dotMeans} ${hasVideos ? 'Hover or focus a dot to preview the meeting; select it to play the recording from the quoted moment.' : hasLinks ? 'Select a dot to open it.' : 'Hover or focus a dot for details.'}`}
        {spec && ` Source: ${spec.source}.`}
        {spec?.note && ` ${spec.note}`}
        {spec && chartKey === 'sites' && city && ' Sites are listed by state only: the source has no city.'}
        {spec && stateName == null && ' National figures, because no state is chosen.'}{' '}
        <a href={docsUrl('/guides/data-stories#sources-and-limits')} target="_blank" rel="noopener noreferrer">
          About this data
        </a>
      </figcaption>
      {spec && (
        <>
          <button
            type="button"
            className="folio-btn"
            aria-expanded={open}
            aria-controls={`stance-data-${round}`}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? 'Hide data table' : 'Show data table'} {open ? '↑' : '↓'}
          </button>
          {open && (
            <DataTable
              id={`stance-data-${round}`}
              caption={`Data table: ${spec.title}, ${scope}`}
              spec={{
                columns: [
                  { label: 'Group' },
                  { label: spec.grandTotal != null ? 'Records' : 'Records shown', numeric: true },
                  { label: spec.grandTotal != null ? 'Share' : 'Share (not known)', numeric: true },
                  { label: 'Dots drawn', numeric: true },
                ],
                rows: spec.groups.map((g) => [g.label, fmt(g.total ?? g.shown), g.share != null ? `${g.share}%` : '—', fmt(g.shown)]),
              }}
            />
          )}
        </>
      )}
    </figure>
  )
}
