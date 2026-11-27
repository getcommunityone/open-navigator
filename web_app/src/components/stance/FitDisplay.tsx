import type { ReactNode } from 'react'
import type { DotsSpec } from '../../utils/stanceGame'
import { countsSentence, specDisplay, topCategories, type CategoryCount } from '../../utils/displayFit'

const fmt = (n: number) => n.toLocaleString('en-US')
/** "data center project" → "data center projects" (the spec's units are all regular). */
const plural = (unit: string, n: number) => (n === 1 ? unit : `${unit}s`)
const whereIn = (scope: string) => (scope === 'National' ? 'nationally' : `in ${scope}`)

/** The records behind a spec, one row each: name (a link when it has a source), status, place and date. */
export function RecordList({ spec, showStatus }: { spec: DotsSpec; showStatus: boolean }) {
  return (
    <ul className="stance-fit-list">
      {spec.groups.flatMap((g) =>
        g.dots.map((d, i) => {
          const meta = [showStatus ? g.label : null, d.place, d.date].filter(Boolean).join(' · ')
          return (
            <li key={`${g.key}-${d.id}-${i}`}>
              {d.url ? (
                <a href={d.url} target="_blank" rel="noopener noreferrer">
                  {d.title}
                </a>
              ) : (
                <span>{d.title}</span>
              )}
              {meta && <span className="stance-fit-meta">{meta}</span>}
            </li>
          )
        }),
      )}
    </ul>
  )
}

/** Sorted horizontal bars labelled with their counts (no percentages); 8 or more categories fold into the top 7 + "Other". */
export function CountBars({ rows, label }: { rows: CategoryCount[]; label: string }) {
  const top = topCategories(rows)
  const max = Math.max(1, ...top.map((r) => r.count))
  return (
    <ol className="stance-fit-bars" aria-label={label}>
      {top.map((r) => (
        <li key={r.label} data-other={r.other ? '' : undefined}>
          <span className="stance-fit-bar-label">{r.label}</span>
          <span className="stance-fit-bar-track" aria-hidden="true">
            <span className="stance-fit-bar" style={{ width: `${(100 * r.count) / max}%` }} />
          </span>
          <span className="stance-fit-bar-n">{fmt(r.count)}</span>
        </li>
      ))}
    </ol>
  )
}

interface Props {
  spec: DotsSpec
  /** "Alabama", "Tuscaloosa, Alabama" or "National". */
  scopeLabel: string
  /** The dot or unit chart, drawn only when the rule picks it (about 20–200 individual items). */
  units: ReactNode
  /** Under the bars (a data table toggle); not shown with a list or a sentence, which already are the data. */
  barsExtra?: ReactNode
}

/**
 * One panel's figure, in the form the shared rule (utils/displayFit) picks from its count (#1289): a list for a handful of
 * records, a sentence for a few counts, sorted count bars for more, the unit chart only for about 20–200 records. No panel
 * picks its own form.
 */
export default function FitDisplay({ spec, scopeLabel, units, barsExtra }: Props) {
  const { display, rows, items } = specDisplay(spec)
  const where = whereIn(scopeLabel)
  // Without a whole-scope total the list may be capped (the source note says so): never state it as the total.
  const lead = `${spec.grandTotal == null ? 'At least ' : ''}${fmt(items)} ${plural(spec.unit, items)} on record ${where}`
  const live = rows.filter((r) => r.count > 0)
  const records = !spec.countsOnly && spec.groups.some((g) => g.dots.length > 0)
  switch (display.kind) {
    case 'empty':
      return null
    case 'list':
      return (
        <div className="stance-fit" data-display="list">
          {records ? (
            <>
              <p className="stance-fit-lead">
                {lead}
                {live.length > 1 ? `. ${countsSentence(rows)}` : ':'}
              </p>
              <RecordList spec={spec} showStatus />
            </>
          ) : (
            <p className="stance-fit-lead">
              {lead}. {live.length > 1 ? countsSentence(rows) : ''}
            </p>
          )}
        </div>
      )
    case 'sentence':
    case 'line':
      return (
        <div className="stance-fit" data-display="sentence">
          <p className="stance-fit-lead">
            {lead}. {countsSentence(rows)}
          </p>
          {records && (
            <details className="stance-fit-more">
              <summary>Show the {fmt(spec.drawn)} {plural(spec.unit, spec.drawn)}</summary>
              <RecordList spec={spec} showStatus />
            </details>
          )}
        </div>
      )
    case 'bars':
    case 'top-bars':
      return (
        <div className="stance-fit" data-display={display.kind}>
          <p className="stance-fit-lead">{lead}.</p>
          <CountBars rows={rows} label={`${spec.title}, ${scopeLabel}`} />
          {barsExtra}
        </div>
      )
    case 'units':
      return (
        <div className="stance-fit" data-display="units">
          {units}
        </div>
      )
  }
}
