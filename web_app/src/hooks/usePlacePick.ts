import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { searchAfterPick } from '../utils/headerPlace'

/** Fired on a place pick (#1191); the home page resets its City / State / National level on it. */
export const PLACE_PICKED_EVENT = 'open-navigator:place-picked'
/** History-state key on the navigation a pick makes; `Layout` remounts the routed page when it sees a new one. */
export const PLACE_PICK_STATE = 'placePickedAt'

/**
 * Apply a place picked in the location dialog (#1191), from the header or the home page: save it, write it into the
 * address (`?state=&city=`; cleared on home, where the saved location is the scope) and tell listeners.
 */
export function usePlacePick(): (loc: LocationData) => void {
  const { setLocation } = useLocationContext()
  const navigate = useNavigate()
  const routerLocation = useLocation()
  return useCallback(
    (loc: LocationData) => {
      setLocation(loc)
      const before = new URLSearchParams(routerLocation.search)
      const next = searchAfterPick(routerLocation.pathname, before, loc)
      if (next.toString() !== before.toString()) {
        const qs = next.toString()
        // The navigation carries a pick marker; Layout remounts the page once this URL has committed (never before it),
        // and only when the scope in the address actually changed.
        navigate(`${routerLocation.pathname}${qs ? `?${qs}` : ''}${routerLocation.hash}`, {
          replace: routerLocation.pathname === '/',
          state: { [PLACE_PICK_STATE]: Date.now() },
        })
      }
      window.dispatchEvent(new CustomEvent(PLACE_PICKED_EVENT, { detail: loc }))
    },
    [setLocation, navigate, routerLocation.pathname, routerLocation.search, routerLocation.hash],
  )
}
