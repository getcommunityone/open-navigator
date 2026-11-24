import { useMemo, useRef, useState, type ReactNode } from 'react'
import { SectionContext, useInViewOnce } from './hooks'
import { FIG_NO } from './data'
import { SECTIONS, type MatrixCtx, type SectionId, type TableSpec } from './types'

/** A real <table> of the rows and values a chart draws (same scope, same formatting). The first column is the row header. */
export function DataTable({ id, caption, spec }: { id: string; caption: string; spec: TableSpec }) {
  return (
    <div className="folio-datatable" id={id}>
      <table className="folio-table folio-table-auto">
        <caption className="folio-sr-only">{caption}</caption>
        <thead>
          <tr>
            {spec.columns.map((c, i) => (
              <th key={i} scope="col" className={c.numeric ? 'text-right' : 'text-left'}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.rows.map((r, ri) => (
            <tr key={ri}>
              {r.map((cell, ci) =>
                ci === 0 ? (
                  <th key={ci} scope="row" className="text-left folio-rowhead">
                    {cell}
                  </th>
                ) : (
                  <td key={ci} className={spec.columns[ci]?.numeric ? 'text-right' : 'text-left'}>
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {spec.rows.length === 0 && <p className="folio-muted">No data available for this view.</p>}
    </div>
  )
}

interface Props {
  ctx: MatrixCtx
  id: SectionId
  /** Headline lines; each slides up in turn (80 ms / 160 ms stagger) when the section first enters view. */
  headline: string[]
  /** Short text column: how to read the figure, with real numbers from the data in scope. */
  text: ReactNode
  /** Per-section controls (above the figure). */
  controls?: ReactNode
  /** The caption after "FIG. NN —", including the scope. */
  caption: ReactNode
  /** The rows the chart draws, for "Show data table". Evaluated only while the table is open. */
  table?: () => TableSpec | null
  /** Put the figure full width under the text (the Table and Heatmap sections). */
  wide?: boolean
  children: ReactNode
}

/**
 * One numbered section of the report, in the reference's spread layout: eyebrow, large headline and text on the left, the
 * figure with its FIG. caption on the right (about 45 / 55 with a hairline between), stacked text-first below 1024 px.
 */
export default function SectionShell({ ctx, id, headline, text, controls, caption, table, wide, children }: Props) {
  const ref = useRef<HTMLElement>(null)
  const seen = useInViewOnce(ref)
  const [el, setEl] = useState<HTMLElement | null>(null)
  const index = SECTIONS.findIndex((s) => s.id === id)
  const name = SECTIONS[index]?.name ?? id
  const num = FIG_NO(index)
  const open = ctx.sp.get('table') === id
  const spec = useMemo(() => (open && table ? table() : null), [open, table])
  return (
    <section
      id={id}
      ref={(n) => {
        const holder = ref as { current: HTMLElement | null }
        holder.current = n
        if (n !== el) setEl(n)
      }}
      className={`folio-section${seen ? ' is-in' : ''}${wide ? ' folio-section-wide' : ''}`}
      aria-labelledby={`${id}-h`}
      data-section={id}
    >
      <div className="folio-spread">
        <div className="folio-spread-text">
          <p className="folio-eyebrow folio-eyebrow-anim">
            {num} — {name}
          </p>
          <h2 className="folio-headline" id={`${id}-h`} tabIndex={-1}>
            {headline.map((line, i) => (
              <span className="folio-line" key={i}>
                <span className="folio-line-inner">{line}</span>
              </span>
            ))}
          </h2>
          <hr className="folio-rule" />
          <div className="folio-body">{text}</div>
        </div>
        <div className="folio-spread-fig">
          {controls && <div className="folio-controls">{controls}</div>}
          <SectionContext.Provider value={{ seen, el }}>
            <div className={`folio-figure${seen ? '' : ' folio-prime'}`}>{children}</div>
          </SectionContext.Provider>
          <p className="folio-fig">
            <b>FIG. {num}</b> — {caption}
          </p>
          {table && (
            <>
              <button
                type="button"
                className="folio-btn"
                aria-expanded={open}
                aria-controls={`${id}-data`}
                onClick={() => ctx.setQP('table', open ? null : id)}
              >
                {open ? 'Hide data table' : 'Show data table'} {open ? '↑' : '↓'}
              </button>
              {open && spec && <DataTable id={`${id}-data`} caption={`Data table: ${name}`} spec={spec} />}
              {open && !spec && <p className="folio-muted" id={`${id}-data`}>No data available for this view.</p>}
            </>
          )}
        </div>
      </div>
    </section>
  )
}
