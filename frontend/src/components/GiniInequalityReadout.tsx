import type { ReactElement } from 'react'
import { GINI_CHOROPLETH_LEGEND_CHIPS, giniLetterGradeFromValue } from '../utils/giniLetterGrade'

/** Compact legend row for map choropleth (raw Gini only). */
export function GiniIncomeInequalityLetterLegend(): ReactElement {
  return (
    <div className="mb-2 rounded-md border border-slate-200/90 bg-white px-2 py-1.5 shadow-sm">
      <p className="mb-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-500">Gini inequality grades</p>
      <p className="mb-1 text-[9px] leading-snug text-slate-600">
        Lower Gini = more equal income spread (A is best). This is not economic efficiency or purchasing power.
      </p>
      <div className="flex flex-wrap items-stretch justify-between gap-1">
        {GINI_CHOROPLETH_LEGEND_CHIPS.map((r) => (
          <div
            key={r.letter}
            className={`flex min-w-0 flex-1 flex-col items-center rounded border px-0.5 py-1 text-center ${r.chipClass}`}
            title={`Letter ${r.letter}: ACS Gini ${r.hint} (household income inequality index)`}
          >
            <span className="text-sm font-black leading-none">{r.letter}</span>
            <span className="mt-0.5 hidden text-[8px] font-medium leading-tight text-slate-600 sm:block">{r.hint}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Scorecard & detail panels: large letter + blurb + numeric ACS value. */
export function GiniIncomeCurrentCell(props: { gini: number; numericText: string }): ReactElement {
  const m = giniLetterGradeFromValue(props.gini)
  if (!m) {
    return <span className="tabular-nums text-slate-400">—</span>
  }
  return (
    <div className="flex flex-col items-end gap-0.5">
      <div className="flex items-center justify-end gap-2">
        <span
          className={`text-3xl font-black leading-none tracking-tight ${m.letterClass}`}
          title={`Gini index ${props.gini.toFixed(3)} — letter reflects inequality spread (lower is more equal)`}
        >
          {m.letter}
        </span>
        <span className={`max-w-[6.5rem] text-right text-[10px] font-semibold leading-tight ${m.blurbClass}`}>{m.blurb}</span>
      </div>
      <span className="text-[10px] tabular-nums text-slate-500">{props.numericText}</span>
    </div>
  )
}
