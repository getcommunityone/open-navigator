import { useEffect, useState } from 'react'

/**
 * Subscribe to a CSS media query and re-render when it flips.
 *
 * SSR/first-paint safe: returns `false` until mounted, then syncs to the real
 * match. Used to pick interaction patterns by viewport (e.g. a swipe carousel
 * on phones vs. a reflow grid on desktop).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia(query)
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches)
    setMatches(mql.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])

  return matches
}

/** True on phone-width viewports (<640px), matching Tailwind's `sm` breakpoint. */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 639px)')
}
