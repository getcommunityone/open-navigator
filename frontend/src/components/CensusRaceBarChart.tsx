import { useEffect, useId, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { formatCensusMapAxisTick } from '../utils/censusMapTransforms'
import { InfoHelpTrigger } from './InfoHelpTrigger'

export type CensusRaceBarRow = {
  id: string
  label: string
  fullName?: string
  value: number
}

function extentForRows(rows: CensusRaceBarRow[]): { min: number; max: number } {
  const vals = rows.map((r) => r.value).filter((x) => Number.isFinite(x))
  if (!vals.length) return { min: 0, max: 1 }
  const rawMin = Math.min(...vals)
  const rawMax = Math.max(...vals)
  const min = Math.min(0, rawMin)
  const max = Math.max(0, rawMax)
  if (min === max) return { min, max: min + 1 }
  return { min, max }
}

function barWidthPercent(value: number, min: number, max: number): number {
  const span = max - min || 1
  return ((value - min) / span) * 100
}

function tickPositionPercent(tickValue: number, min: number, max: number): number {
  const span = max - min || 1
  return ((tickValue - min) / span) * 100
}

const AXIS_TICK_COUNT = 6

/** Try newest plate first, then SVG flag heroes (wikicommons export), then legacy ``/data/state-symbols/``. */
function winnerVisualCandidates(usps: string): string[] {
  const w = `/data/wikicommons/${usps}`
  const latest = (['png', 'jpg', 'jpeg', 'webp', 'svg'] as const).map((ext) => `${w}_latest.${ext}`)
  const heroes = [`${w}_colors_hero.svg`, `${w}_colors_hero.jpg`]
  const legacy = [`/data/state-symbols/${usps}_colors_hero.jpg`, `/data/state-symbols/${usps}_colors_hero.svg`]
  return [...latest, ...heroes, ...legacy]
}

type CensusRaceBarChartProps = {
  rows: CensusRaceBarRow[]
  formatValue: (v: number) => string
  formatBarEnd?: (v: number) => string
  formatAxisTick?: (n: number, valueSpan?: number) => string
  playing?: boolean
  /** USPS code for the #1 row (US map: top state). Used when ``leaderPlateUsps`` is not set. */
  winnerUsps?: string | null
  /** When drilling counties/places, show this **state’s** plate at the top while #1 may be a county/city. */
  leaderPlateUsps?: string | null
  /** Shown beside the winner row (e.g. selected map year). */
  vintageYear?: string | null
  /** Tooltip for the year badge (ACS window labeling). */
  yearHelp?: string | null
  /** Subtitle under the #1 headline explaining rank direction for the metric. */
  winnerCaption?: string | null
  /** Full metric dictionary + ranking copy for the (i) next to the #1 headline. */
  winnerMetricHelp?: string | null
  readingCalloutTitle?: string | null
  readingCalloutLines?: string[] | null
  className?: string
  /** When set, the matching row is outlined (paired with map highlight from the parent). */
  selectedRowId?: string | null
  /** Click a bar to select/deselect; parent syncs highlight on the map. */
  onRowClick?: (rowId: string) => void
}

export function CensusRaceBarChart({
  rows,
  formatValue,
  formatBarEnd,
  formatAxisTick = formatCensusMapAxisTick,
  playing = false,
  winnerUsps,
  leaderPlateUsps = null,
  vintageYear = null,
  yearHelp = null,
  winnerCaption = null,
  winnerMetricHelp = null,
  readingCalloutTitle = 'How to read this chart',
  readingCalloutLines = null,
  className = '',
  selectedRowId = null,
  onRowClick,
}: CensusRaceBarChartProps) {
  const reduced = useReducedMotion()
  const [heroAttempt, setHeroAttempt] = useState(0)
  const readingPanelId = useId()
  const [readingOpen, setReadingOpen] = useState(false)

  const { min, max } = useMemo(() => extentForRows(rows), [rows])
  const valueSpan = max - min
  const ticks = useMemo(() => {
    return Array.from({ length: AXIS_TICK_COUNT }, (_, i) => min + (i / (AXIS_TICK_COUNT - 1)) * (max - min))
  }, [min, max])

  const winner = rows[0]
  const plateUsps = leaderPlateUsps ?? winnerUsps ?? null
  const heroCandidates = plateUsps ? winnerVisualCandidates(plateUsps) : []
  const heroUrl = heroAttempt < heroCandidates.length ? heroCandidates[heroAttempt] : undefined

  useEffect(() => {
    setHeroAttempt(0)
  }, [plateUsps, winner?.id])

  const rowTransition = reduced
    ? { duration: 0.12, ease: 'easeOut' as const }
    : playing
      ? { type: 'spring' as const, stiffness: 260, damping: 34, mass: 0.82 }
      : { type: 'spring' as const, stiffness: 400, damping: 36, mass: 0.72 }

  const fmtEnd = formatBarEnd ?? formatValue

  const widthTransition = reduced
    ? { duration: 0.12, ease: 'easeOut' as const }
    : playing
      ? { type: 'spring' as const, stiffness: 200, damping: 28, mass: 0.88 }
      : { type: 'spring' as const, stiffness: 340, damping: 32, mass: 0.78 }

  /** Tight label + value columns so the bar track uses most of the card width. */
  const gridCols = 'minmax(5.25rem, 7.25rem) minmax(0, 1fr) 2.35rem'

  return (
    <div className={`flex w-full min-w-0 max-w-full flex-col ${className}`}>
      {readingCalloutLines?.length ? (
        <div className="mb-2 w-full">
          <button
            type="button"
            className="mb-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
            aria-expanded={readingOpen}
            aria-controls={readingPanelId}
            onClick={() => setReadingOpen((v) => !v)}
          >
            <span>{readingCalloutTitle ?? 'How to read this chart'}</span>
            <span
              className={`text-[10px] text-slate-500 transition-transform ${readingOpen ? 'rotate-180' : ''}`}
              aria-hidden
            >
              ▼
            </span>
          </button>
          {readingOpen ? (
            <div
              id={readingPanelId}
              className="w-full rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2"
              role="region"
              aria-label={readingCalloutTitle ?? 'How to read this chart'}
            >
              <ul className="space-y-1 text-xs text-slate-800 leading-snug">
                {readingCalloutLines.map((line, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-semibold text-amber-700 select-none" aria-hidden>
                      ·
                    </span>
                    <span className="min-w-0 flex-1">{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {winner ? (
        <div className="mb-3 flex w-full min-w-0 flex-col gap-2 border-b border-slate-200 pb-3 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <div className="flex min-w-0 flex-1 flex-row items-start gap-3">
            {heroUrl ? (
              <div className="group relative w-[min(7.5rem,32%)] shrink-0 sm:w-28">
                <div className="rounded-lg bg-gradient-to-br from-slate-300/90 via-slate-100 to-zinc-200 p-[2px] shadow-md ring-1 ring-slate-500/20">
                  <div className="rounded-md bg-gradient-to-b from-white/90 to-slate-200/80 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
                    <div
                      className="relative w-full overflow-hidden rounded bg-[linear-gradient(180deg,#f8fafc_0%,#e2e8f0_55%,#cbd5e1_100%)] ring-1 ring-slate-900/10"
                      style={{ aspectRatio: '2.06 / 1' }}
                    >
                      <img
                        src={heroUrl}
                        alt={`${plateUsps ?? ''} — reference license plate art`}
                        className={`absolute inset-0 h-full w-full object-contain object-center p-0.5 drop-shadow-[0_2px_6px_rgba(15,23,42,0.15)] transition-[transform,filter] duration-300 ease-out ${
                          reduced ? '' : 'group-hover:scale-[1.02] group-hover:drop-shadow-[0_4px_12px_rgba(15,23,42,0.2)]'
                        }`}
                        loading="lazy"
                        decoding="async"
                        onError={() => setHeroAttempt((a) => a + 1)}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <div className="text-sm font-extrabold leading-tight tracking-tight text-slate-900">#1 for this metric</div>
                {winnerMetricHelp ? (
                  <InfoHelpTrigger
                    topic="Top rank on this metric"
                    align="left"
                    help={winnerMetricHelp}
                    buttonClassName="rounded p-0.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52]"
                  />
                ) : null}
              </div>
              {winnerCaption ? (
                <div className="mt-0.5 text-[10px] font-semibold leading-snug text-slate-600">{winnerCaption}</div>
              ) : null}
              <div className="mt-1 text-sm font-bold leading-snug text-slate-950">{winner.fullName ?? winner.label}</div>
              <div className="mt-0.5 text-xs font-extrabold tabular-nums text-slate-800">{formatValue(winner.value)}</div>
            </div>
          </div>
          {vintageYear != null && vintageYear !== '' ? (
            <div className="census-map-year-badge flex shrink-0 flex-row items-center gap-1.5 self-start rounded-xl border border-slate-300 bg-white px-2.5 py-1 shadow-md sm:ml-auto">
              <div className="flex flex-row items-baseline gap-2">
                <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500">Year</span>
                <span className="text-xl font-extrabold tabular-nums leading-none text-slate-900">{vintageYear}</span>
              </div>
              {yearHelp ? <InfoHelpTrigger help={yearHelp} topic="ACS year" align="right" /> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-2 overflow-x-hidden overflow-y-visible py-0.5">
        {rows.map((r) => {
          const pct = barWidthPercent(r.value, min, max)
          const tip = `${r.fullName ?? r.label}: ${formatValue(r.value)}`
          const selected = selectedRowId != null && selectedRowId === r.id
          return (
            <motion.div
              key={r.id}
              layout={!reduced}
              title={tip}
              transition={rowTransition}
              role={onRowClick ? 'button' : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onClick={onRowClick ? () => onRowClick(r.id) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onRowClick(r.id)
                      }
                    }
                  : undefined
              }
              className={`grid w-full max-w-full min-w-0 shrink-0 items-center gap-x-2 rounded-md outline-none ${
                onRowClick ? 'cursor-pointer hover:bg-slate-50/90 focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-1' : ''
              } ${selected ? 'bg-amber-50/80 ring-2 ring-amber-500/85 ring-inset' : ''}`}
              style={{ gridTemplateColumns: gridCols }}
            >
              <div className="min-w-0 justify-self-stretch text-right text-[11px] font-semibold leading-snug text-slate-900 break-words hyphens-auto [overflow-wrap:anywhere]">
                {r.label}
              </div>
              <div className="relative h-[22px] min-h-[22px] min-w-0 w-full max-w-full overflow-hidden rounded-md bg-slate-100 ring-1 ring-slate-200/80">
                <motion.div
                  layout={false}
                  className="h-full rounded-r-md bg-[#3d5c55] shadow-inner"
                  initial={false}
                  animate={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
                  transition={widthTransition}
                />
              </div>
              <div className="min-w-0 justify-self-end text-right text-[8.5px] font-bold tabular-nums leading-none text-slate-700">
                {fmtEnd(r.value)}
              </div>
            </motion.div>
          )
        })}
      </div>

      <div
        className="mt-2 grid w-full max-w-full min-w-0 shrink-0 gap-x-2 border-t border-slate-200 pt-2"
        style={{ gridTemplateColumns: gridCols }}
      >
        <div aria-hidden />
        <div className="relative min-h-[2.35rem] min-w-0 max-w-full">
          <div className="pointer-events-none absolute inset-x-0 top-0 border-b border-slate-500" />
          {ticks.map((t, i) => {
            const n = ticks.length
            const isFirst = i === 0
            const isLast = i === n - 1
            const leftPct = tickPositionPercent(t, min, max)
            const style: CSSProperties = isFirst
              ? { left: 0, transform: 'none' }
              : isLast
                ? { left: '100%', transform: 'translateX(-100%)' }
                : { left: `${leftPct}%`, transform: 'translateX(-50%)' }
            const alignItems: 'flex-start' | 'flex-end' | 'center' = isFirst ? 'flex-start' : isLast ? 'flex-end' : 'center'
            const textClass = isFirst ? 'text-left' : isLast ? 'text-right' : 'text-center'
            return (
              <div key={i} className="absolute top-0 flex flex-col" style={{ ...style, alignItems }}>
                <span className="h-2 w-px shrink-0 bg-slate-600" aria-hidden />
                <span
                  className={`mt-1 max-w-[3.75rem] text-[9px] font-semibold tabular-nums leading-tight text-slate-600 ${textClass}`}
                >
                  {formatAxisTick(t, valueSpan)}
                </span>
              </div>
            )
          })}
        </div>
        <div aria-hidden />
      </div>
    </div>
  )
}
