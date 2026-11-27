import type { PhonePlaceState } from '../utils/headerPlace'

export interface PlaceScopeToggleProps {
  state: PhonePlaceState
  /** Open the place picker: from "Find your town", or from the place half while it is already the active scope. */
  onPickPlace: () => void
  /** Switch scope: the place half while National is active, or the National half. */
  onSwitch: (target: 'place' | 'national') => void
}

/**
 * The header's one place control (#1331), on desktop and phones: a rounded pill with two halves, "📍 Town, ST" and
 * "National". The active half is filled teal; the inactive half is white with teal text. The place half, when already
 * active, opens the picker (hence the ▾); while National is active it returns to the saved place.
 */
export function PlaceScopeToggle({ state, onPickPlace, onSwitch }: PlaceScopeToggleProps) {
  if (state.mode === 'zip') {
    return (
      <div className="sh-ptoggle" role="group" aria-label="Place for this page" data-testid="header-place-toggle">
        <button
          type="button"
          className="sh-ptoggle-btn"
          data-side="place"
          aria-pressed="false"
          aria-haspopup="dialog"
          aria-label="Find your town"
          title="Find your town"
          onClick={onPickPlace}
        >
          <span aria-hidden="true">📍</span>
          <span className="sh-ptoggle-text">Find your town</span>
        </button>
      </div>
    )
  }
  const placeActive = state.active === 'place'
  const name = state.place
  return (
    <div className="sh-ptoggle" role="group" aria-label="Place for this page" data-testid="header-place-toggle">
      <button
        type="button"
        className="sh-ptoggle-btn"
        data-side="place"
        aria-pressed={placeActive}
        aria-haspopup={placeActive ? 'dialog' : undefined}
        aria-label={placeActive ? `${name}. Change town` : `Show ${name}`}
        title={placeActive ? `${name} (change town)` : `Show ${name}`}
        onClick={() => (placeActive ? onPickPlace() : onSwitch('place'))}
      >
        <span aria-hidden="true">📍</span>
        <span className="sh-ptoggle-text">{name}</span>
        {placeActive && (
          <span aria-hidden="true" className="sh-ptoggle-caret">
            ▾
          </span>
        )}
      </button>
      {state.canToggle && (
        <button
          type="button"
          className="sh-ptoggle-btn"
          data-side="national"
          aria-pressed={!placeActive}
          title="Show national data"
          onClick={() => placeActive && onSwitch('national')}
        >
          National
        </button>
      )}
    </div>
  )
}
