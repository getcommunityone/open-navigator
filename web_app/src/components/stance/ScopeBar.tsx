import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import PlaceControl from './PlaceControl'

interface Props {
  /** The crumb link back to where the reader came from. */
  backTo: string
  backLabel: string
  /** The page title: the page's `h1` when `titleAsH1`, otherwise plain text (the challenge's `h1` is on its cover). */
  title: string
  titleAsH1?: boolean
  /** What the scope label sits after, for example "Data Center Story". */
  scopeLead?: string
  /** Exactly what the data shows: "National", "Alabama", "Tuscaloosa, Alabama". */
  label: string
  stateCode: string | undefined
  stateName: string | null
  city: string | null
  /** The short word of the screen in view (a category, never a number). */
  current: string
  /** A sentence heading (the page's h1, its blanks are the controls); replaces the title and the Your place button. */
  heading?: ReactNode
  /** Extra controls in the bar, before "Your place" (the challenge's sound switch). */
  extra?: ReactNode
  /** The strip of progress pips along the bar's lower edge. */
  progress?: ReactNode
  placeOpen: boolean
  onPlaceOpenChange: (open: boolean) => void
  onApply: (stateCode: string | null, city: string | null) => void
}

/** The sticky bar above the screens: where you are, the scope label with its broaden controls, and "Your place". */
export default function ScopeBar(p: Props) {
  return (
    <header className="stance-top">
      <div className="stance-top-text">
        {p.heading ? (
          <div className="stance-heading-row">{p.heading}</div>
        ) : (
          <div className="stance-crumbs">
            <Link to={p.backTo}>{p.backLabel}</Link>
            <span aria-hidden="true">·</span>
            {p.titleAsH1 ? <h1 className="stance-title">{p.title}</h1> : <span>{p.title}</span>}
          </div>
        )}
        {/* With the United States in the sentence blank, skip Showing: National (#959). Keep the back crumb and broaden controls when a place is set. */}
        {(p.heading || p.stateName) && (
          <p className="stance-scope" data-testid="stance-scope">
            {p.heading && (
              <>
                <Link to={p.backTo}>{p.backLabel}</Link>
                {p.stateName ? ' · ' : null}
              </>
            )}
            {p.stateName ? (
              <>
                {p.scopeLead ? `${p.scopeLead} · showing:` : 'Showing:'} <b>{p.label}</b>
                {p.city && (
                  <button type="button" className="folio-link-btn" onClick={() => p.onApply(p.stateCode ?? null, null)}>
                    All of {p.stateName}
                  </button>
                )}
                <button type="button" className="folio-link-btn" onClick={() => p.onApply(null, null)}>
                  National only
                </button>
              </>
            ) : null}
          </p>
        )}
      </div>
      <p className="stance-counter" data-testid="stance-current">
        {p.current}
      </p>
      {p.extra}
      {p.progress}
      {!p.heading && <PlaceControl stateCode={p.stateCode} city={p.city} open={p.placeOpen} onOpenChange={p.onPlaceOpenChange} onApply={p.onApply} />}
    </header>
  )
}
