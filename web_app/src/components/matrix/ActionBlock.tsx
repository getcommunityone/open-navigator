import { Link } from 'react-router-dom'
import { adjacentScreens, screenLabel } from '../../utils/matrixStory'
import type { MatrixCtx } from './types'

/** The app's decisions browse page (App.tsx `browse-topics`); it reads `?state=<2-letter code>` and is national without it. */
const DECISIONS_PATH = '/browse-topics'

/** Where "See decisions" goes: the state in scope, or the national page. Exported for the tests. */
export function decisionsHref(stateCode: string | null): string {
  return stateCode ? `${DECISIONS_PATH}?${new URLSearchParams({ state: stateCode }).toString()}` : DECISIONS_PATH
}

/**
 * The last screen: large square buttons that carry the scope in view. Every destination is a route that
 * exists in App.tsx. The Table section's own CSV download is the third button.
 */
export default function ActionBlock({ ctx, onDownload }: { ctx: MatrixCtx; onDownload: () => void }) {
  const state = ctx.stateScope
  const { prev } = adjacentScreens('action')
  return (
    <section className="folio-action" id="action" aria-labelledby="action-h">
      <p className="folio-eyebrow">Go further</p>
      <h3 className="folio-action-title" id="action-h" tabIndex={-1}>
        Take it further
      </h3>
      <p className="folio-lede">
        {ctx.metricLabel}, {ctx.vintage} ACS 5-year, {state ? state.name : 'all states and territories'}.
      </p>
      <ul className="folio-action-grid">
        <li>
          <Link className="folio-action-btn" to={decisionsHref(state?.code ?? null)}>
            <span className="folio-action-label">{state ? `See decisions in ${state.name}` : 'See decisions nationwide'}</span>
            <span aria-hidden="true" className="folio-action-arrow">
              →
            </span>
          </Link>
        </li>
        <li>
          <button type="button" className="folio-action-btn" onClick={onDownload}>
            <span className="folio-action-label">Download this table (CSV)</span>
            <span aria-hidden="true" className="folio-action-arrow">
              ↓
            </span>
          </button>
        </li>
        <li>
          <Link className="folio-action-btn" to={ctx.mapHref}>
            <span className="folio-action-label">Open the map view</span>
            <span aria-hidden="true" className="folio-action-arrow">
              →
            </span>
          </Link>
        </li>
      </ul>
      <div className="folio-pager folio-pager-end">
        {prev && (
          <button type="button" className="folio-pager-back" onClick={() => ctx.goTo(prev.domId)}>
            <span aria-hidden="true">↑</span> Back: {screenLabel(prev.section, ctx.labelInput)}
          </button>
        )}
        <button type="button" className="folio-pager-back" onClick={() => ctx.goTo('top')}>
          <span aria-hidden="true">↑</span> Back to the start
        </button>
      </div>
    </section>
  )
}
