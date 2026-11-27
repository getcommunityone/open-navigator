import { useEffect, useState, type RefObject } from 'react'

/** Phones only: the width stance.css stacks a screen at. */
const PHONE = '(max-width: 767px)'
/** Room kept for the "More" button under the panel, with the gap above it. */
const MORE_ROOM = 64
/** The smallest a first block is zoomed to before it is left to the "More" view. */
const MIN_ZOOM = 0.55

/**
 * Fit one story screen above the fixed bottom bar on a phone (#1290, owner screenshot 27 Nov 2026: "Not fitting on phone by
 * default."). The headline and its line stay; the panel keeps its blocks in order while they fit in the room left above the
 * bar, the first block zoomed down if it alone is too tall; every later block, and the screen's own extras under the panel
 * (the statement, the Overview's notes), wait behind "More" (`more` true shows everything, with scrolling, as before).
 * Returns whether anything is waiting. Nothing is hidden on a wider screen.
 */
export function useScreenFit(sectionRef: RefObject<HTMLElement | null>, rightRef: RefObject<HTMLElement | null>, active: boolean, more: boolean): boolean {
  const [hasMore, setHasMore] = useState(false)
  useEffect(() => {
    const section = sectionRef.current
    const right = rightRef.current
    if (!section || !right || typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia(PHONE)
    let frame = 0

    const reset = () => {
      section.querySelectorAll<HTMLElement>('.fit-hidden').forEach((e) => e.classList.remove('fit-hidden'))
      section.querySelectorAll<HTMLElement>('[data-fit-zoom]').forEach((e) => {
        e.style.removeProperty('zoom')
        e.removeAttribute('data-fit-zoom')
      })
    }
    /** The panel's blocks, in order: a wrapper with several blocks counts as its blocks. */
    const blocks = (el: Element, room: number, depth = 0): HTMLElement[] => {
      const kids = [...el.children].filter((k): k is HTMLElement => k instanceof HTMLElement && !k.classList.contains('stance-screen-more'))
      return kids.flatMap((k) => {
        const tall = k.getBoundingClientRect().height > room
        const inner = [...k.children].filter((c) => c instanceof HTMLElement && c.getBoundingClientRect().height > 0)
        return tall && depth < 3 && inner.length > 1 && !(k instanceof SVGElement) && !k.matches('svg, canvas, ul, ol, dl, table')
          ? blocks(k, room, depth + 1)
          : [k]
      })
    }
    const measure = () => {
      frame = 0
      reset()
      if (!mq.matches || more || !active) {
        setHasMore(false)
        return
      }
      // Measured in the screen's own coordinates, as if it sat in its snap place (under the top bars), so a page still
      // landing or mid-swipe measures the same room.
      const bar = document.querySelector('[data-testid="story-bottombar"]')
      const grid = section.querySelector('.stance-grid')
      const sTop = section.getBoundingClientRect().top
      const margin = parseFloat(getComputedStyle(section).scrollMarginTop || '0') || 0
      const barAt = (bar ? bar.getBoundingClientRect().top : window.innerHeight) - margin
      const gridAt = grid
        ? grid.getBoundingClientRect().top - sTop + grid.clientHeight - (parseFloat(getComputedStyle(grid).paddingBottom || '0') || 0)
        : Infinity
      const rightAt = right.getBoundingClientRect().top - sTop
      const top = right.getBoundingClientRect().top
      let hidden = false
      // The screen's extras after the panel on a phone (statement, notes, broaden is before it and stays).
      const left = section.querySelector('.stance-left')
      for (const el of left ? [...left.children] : []) {
        if (el instanceof HTMLElement && !el.matches('.stance-card, .stance-head, .stance-nav, .stance-broaden') && el.getBoundingClientRect().height > 0) {
          el.classList.add('fit-hidden')
          hidden = true
        }
      }
      const room = Math.min(barAt, gridAt) - rightAt - MORE_ROOM
      const list = blocks(right, room).filter((b) => b.getBoundingClientRect().height > 0)
      list.forEach((b, i) => {
        if (i === 0) return
        if (b.getBoundingClientRect().bottom - top > room) {
          b.classList.add('fit-hidden')
          hidden = true
        }
      })
      const first = list[0]
      if (first) {
        const h = first.getBoundingClientRect().height
        if (h > room && room > 0) {
          const z = Math.max(MIN_ZOOM, room / h)
          first.style.setProperty('zoom', String(Math.floor(z * 100) / 100))
          first.setAttribute('data-fit-zoom', '')
          if (first.getBoundingClientRect().bottom - top > room) {
            // Still too tall at the smallest zoom: it waits behind "More" like the rest, so the screen never runs under the bar.
            first.style.removeProperty('zoom')
            first.removeAttribute('data-fit-zoom')
            first.classList.add('fit-hidden')
          }
          hidden = true
        }
      }
      setHasMore(hidden)
    }
    // A re-measure after our own change lands on the same result and the same size, so the observers settle.
    const schedule = () => {
      if (frame) return
      frame = requestAnimationFrame(measure)
    }
    measure()
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(schedule) : null
    ro?.observe(right)
    const mo = typeof MutationObserver !== 'undefined' ? new MutationObserver(schedule) : null
    mo?.observe(right, { childList: true, subtree: true })
    window.addEventListener('resize', schedule)
    mq.addEventListener?.('change', schedule)
    // Late layout (fonts, the screen sliding in): measure again once things settle.
    const lates = [600, 1500, 3000, 6000, 10_000].map((ms) =>
      window.setTimeout(schedule, ms),
    )
    return () => {
      ro?.disconnect()
      mo?.disconnect()
      window.removeEventListener('resize', schedule)
      mq.removeEventListener?.('change', schedule)
      lates.forEach((t) => window.clearTimeout(t))
      if (frame) cancelAnimationFrame(frame)
      reset()
    }
  }, [sectionRef, rightRef, active, more])
  return hasMore
}
