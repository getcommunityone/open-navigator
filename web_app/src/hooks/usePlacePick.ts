import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { searchAfterPick } from '../utils/headerPlace'

/** Fired after a place pick so pages that read the place once (on mount) can follow it (#1191). */
export const PLACE_PICKED_EVENT = 'open-navigator:place-picked'

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
        navigate(`${routerLocation.pathname}${qs ? `?${qs}` : ''}${routerLocation.hash}`, { replace: routerLocation.pathname === '/' })
      }
      // After the navigation has rendered, so a page remounted on this event reads the new address.
      window.setTimeout(() => window.dispatchEvent(new CustomEvent(PLACE_PICKED_EVENT, { detail: loc })), 0)
    },
    [setLocation, navigate, routerLocation.pathname, routerLocation.search, routerLocation.hash],
  )
}
