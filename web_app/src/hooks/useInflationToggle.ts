/**
 * useInflationToggle — Nominal / Real mode for dollar charts, persisted in
 * localStorage so the user's preference survives page reloads.
 *
 * Default = ``'real'`` to match the mockup (and the "honest dollars"
 * framing): a $100K income in 2010 isn't the same $100K in 2025. Users who
 * want the headline as-published can flip to Nominal and the state sticks.
 *
 * Storage key is namespaced so it doesn't collide with other UI prefs;
 * cross-tab updates propagate via the ``storage`` event so flipping the
 * toggle in one tab updates every other open tab too.
 */
import { useCallback, useEffect, useState } from 'react'

export type InflationMode = 'nominal' | 'real'

const STORAGE_KEY = 'open_navigator:inflation_mode'
const DEFAULT_MODE: InflationMode = 'real'

function readStored(): InflationMode {
  if (typeof window === 'undefined') return DEFAULT_MODE
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    return v === 'nominal' || v === 'real' ? v : DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

export function useInflationToggle(): {
  mode: InflationMode
  setMode: (next: InflationMode) => void
  toggle: () => void
} {
  const [mode, setModeState] = useState<InflationMode>(readStored)

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY) return
      const next = e.newValue === 'nominal' || e.newValue === 'real' ? e.newValue : DEFAULT_MODE
      setModeState(next)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setMode = useCallback((next: InflationMode) => {
    setModeState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // private mode / storage quota — silently keep in-memory state
    }
  }, [])

  const toggle = useCallback(() => {
    setMode(mode === 'real' ? 'nominal' : 'real')
  }, [mode, setMode])

  return { mode, setMode, toggle }
}
