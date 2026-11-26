import type { MouseEvent } from 'react'

/**
 * "Skip to main content" (#1146, WCAG 2.4.1): the first tab stop on every page, hidden until focused. It moves focus to the
 * page's <main> (`#main-content` where a layout sets it), so a keyboard user skips the header's links.
 */
export default function SkipLink() {
  const skip = (e: MouseEvent<HTMLAnchorElement>) => {
    const main = document.getElementById('main-content') ?? document.querySelector<HTMLElement>('main')
    if (!main) return
    e.preventDefault()
    if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1')
    main.focus({ preventScroll: true })
    main.scrollIntoView({ block: 'start' })
  }
  return (
    <a href="#main-content" className="skip-link" onClick={skip}>
      Skip to main content
    </a>
  )
}
