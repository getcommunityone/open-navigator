import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * ScrollToTop scrolls the window to the top whenever the route pathname
 * changes. This guarantees that navigating to a new page (e.g. arriving at the
 * home page from anywhere) starts at the top instead of preserving the previous
 * scroll position.
 *
 * Exception: when the destination URL carries a hash (e.g. `/#impact`,
 * `/explore#explore-build`), the page owns an in-page anchor scroll, so we skip
 * the reset and let that behavior win.
 *
 * The reset uses `behavior: 'instant'` to override the global
 * `html { scroll-behavior: smooth }` rule — a smooth animation on every route
 * change gets interrupted as the new page's content loads and frequently never
 * reaches the top. An instant jump lands at the top immediately.
 */
export default function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) return
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior })
  }, [pathname, hash])

  return null
}
