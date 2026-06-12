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
 */
export default function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) return
    window.scrollTo(0, 0)
  }, [pathname, hash])

  return null
}
