import type { ReactElement } from 'react'
import { GINI_LETTER_STRIP } from '../utils/giniLetterGrade'

const TREND_LEGEND = [
  { icon: '↑↑', label: 'Strong improvement', className: 'text-emerald-700' },
  { icon: '↑', label: 'Slight improvement', className: 'text-emerald-600' },
  { icon: '→', label: 'Flat', className: 'text-slate-500' },
  { icon: '↓', label: 'Slight decline', className: 'text-amber-700' },
  { icon: '↓↓', label: 'Notable decline', className: 'text-rose-700' },
] as const

/** Trend arrows for the scorecard table (see copy: area ACS change, not benchmark). */
export function ScorecardTrendLegend(): ReactElement {
  return (
    <div className="rounded-lg border border-slate-300/80 bg-white px-2.5 py-1.5 shadow-sm sm:px-3">
      <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-slate-500">How to read this page</p>
      <div>
        <p className="mb-0.5 text-[10px] font-semibold text-slate-600">This area’s trend column</p>
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[10px] leading-tight">
          {TREND_LEGEND.map((row) => (
            <span key={row.icon} className="inline-flex items-center gap-1 whitespace-nowrap">
              <span className={`font-mono text-sm font-bold ${row.className}`}>{row.icon}</span>
              <span className="font-medium text-slate-700">{row.label}</span>
            </span>
          ))}
        </div>
        <p className="mt-1.5 text-[9px] leading-snug text-slate-600">
          <span className="font-semibold text-slate-700">Not vs benchmark.</span> Arrows follow percent change in{' '}
          <span className="font-semibold">this area’s</span> published ACS estimate (↑ rose, ↓ fell). “Strong / Slight” is
          move size (about 8%+ absolute change = strong / double arrow). “Improvement / decline” and the Favorable chip mean
          that move is good or bad <span className="font-semibold">for that metric’s direction</span> (e.g. higher income
          usually better; longer commute usually worse)—independent of the U.S. / region / state benchmark.
        </p>
        <p className="mt-1 text-[9px] leading-snug text-slate-600">
          The <span className="font-semibold">vs.</span> column is where benchmark shows up (today’s level and optional pace
          vs benchmark). <span className="font-semibold">Section letter</span> grades count favorable{' '}
          <span className="font-semibold">area</span> trends only; switching benchmark does not recalculate them.
        </p>
      </div>
    </div>
  )
}

/** Gini A–F strip for the Gini table row (shown at the bottom of the scorecard). */
export function ScorecardGiniLegend(): ReactElement {
  return (
    <div className="rounded-lg border border-slate-300/80 bg-white px-2.5 py-1.5 shadow-sm sm:px-3">
      <p className="mb-1 text-[10px] font-semibold text-slate-600">Gini inequality (A–F on the Gini row)</p>
      <div className="flex flex-col gap-1.5 text-[10px] leading-snug sm:flex-row sm:flex-wrap sm:items-baseline">
        <div className="flex flex-wrap items-baseline gap-x-0.5 gap-y-1">
          {GINI_LETTER_STRIP.map((row, i) => (
            <span key={row.letter} className="inline-flex items-baseline gap-0.5 whitespace-nowrap">
              {i > 0 ? (
                <span className="px-0.5 font-normal text-slate-300" aria-hidden>
                  ·
                </span>
              ) : null}
              <span className={`text-base font-black leading-none ${row.letterClass}`}>{row.letter}</span>
              {row.tail ? <span className="font-medium text-slate-700">{row.tail}</span> : null}
            </span>
          ))}
        </div>
        <p className="text-[9px] font-normal text-slate-500 sm:max-w-md">
          <span className="font-semibold text-slate-600">(Gini grades)</span> Lower numeric Gini = more equal spread (A
          is best). Not “efficiency.”
        </p>
      </div>
    </div>
  )
}

/** Full-page legend: trend block then Gini block (prefer using Trend + Gini separately on the scorecard). */
export function ScorecardTrendAndGiniLegend(): ReactElement {
  return (
    <div className="space-y-2">
      <ScorecardTrendLegend />
      <ScorecardGiniLegend />
    </div>
  )
}
