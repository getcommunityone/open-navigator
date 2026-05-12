import type { ReactElement } from 'react'
import { GINI_LETTER_STRIP } from '../utils/giniLetterGrade'

const TREND_LEGEND = [
  { icon: '↑↑', label: 'Strong improvement', className: 'text-emerald-700' },
  { icon: '↑', label: 'Slight improvement', className: 'text-emerald-600' },
  { icon: '→', label: 'Flat', className: 'text-slate-500' },
  { icon: '↓', label: 'Slight decline', className: 'text-amber-700' },
  { icon: '↓↓', label: 'Notable decline', className: 'text-rose-700' },
] as const

/**
 * Scorecard key: trend arrows (for metrics with a clear “better” direction) and Gini A–F
 * (inequality spread — not dollars, not “efficiency”).
 */
export function ScorecardTrendAndGiniLegend(): ReactElement {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm sm:px-4">
      <p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-slate-500">How to read this page</p>
      <div className="space-y-2.5">
        <div>
          <p className="mb-1 text-[10px] font-semibold text-slate-600">Trend (scored metrics)</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[10px] leading-tight">
            {TREND_LEGEND.map((row) => (
              <span key={row.icon} className="inline-flex items-center gap-1 whitespace-nowrap">
                <span className={`font-mono text-sm font-bold ${row.className}`}>{row.icon}</span>
                <span className="font-medium text-slate-700">{row.label}</span>
              </span>
            ))}
          </div>
        </div>
        <div className="border-t border-slate-100 pt-2.5">
          <p className="mb-1 text-[10px] font-semibold text-slate-600">Gini inequality (same row as median income)</p>
          <div className="flex flex-wrap items-baseline gap-x-0.5 gap-y-1 text-[10px] leading-snug">
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
            <span className="basis-full pl-0 text-[9px] font-normal text-slate-500 sm:basis-auto sm:pl-2">
              <span className="font-semibold text-slate-600">(Gini grades)</span> Lower numeric Gini = more equal spread
              (A is best). Not “efficiency.”
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
