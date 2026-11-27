import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import { PLACE_PICK_STATE } from '../hooks/usePlacePick'
import { phonePlaceState, searchForScope } from '../utils/headerPlace'
import { PlaceScopeToggle } from './PlaceScopeToggle'

/** The place/National toggle wired to the router and the saved location (#1331); the picker is the header's. */
export default function HeaderPlaceScope({ onPickPlace }: { onPickPlace: () => void }) {
  const routerLocation = useLocation()
  const navigate = useNavigate()
  const { location: saved } = useLocationContext()
  // The place just left for National, kept for this visit only (never saved): one tap back works after a deep link with
  // nothing saved, and returns to the place the page had, not a different saved town.
  const [back, setBack] = useState<{ state: string; city: string | null } | null>(null)
  const town = back ?? saved
  const search = new URLSearchParams(routerLocation.search)
  const state = phonePlaceState(routerLocation.pathname, search, town)
  // A pick changes the saved place; the place left for National is no longer the one to return to.
  useEffect(() => setBack(null), [saved])

  const toggle = (target: 'place' | 'national') => {
    if (target === 'national') {
      const st = (search.get('state') ?? '').trim().toUpperCase()
      if (st) setBack({ state: st, city: (search.get('city') ?? '').trim() || null })
    }
    const next = searchForScope(routerLocation.pathname, search, target, town)
    if (next.toString() === search.toString()) return
    const qs = next.toString()
    // The same pick marker as a town pick: Layout remounts the page once this URL commits, so label and data move together.
    navigate(`${routerLocation.pathname}${qs ? `?${qs}` : ''}${routerLocation.hash}`, {
      replace: routerLocation.pathname === '/',
      state: { [PLACE_PICK_STATE]: Date.now() },
    })
  }

  return <PlaceScopeToggle state={state} onPickPlace={onPickPlace} onSwitch={toggle} />
}
