import { useEffect, useState, type RefObject } from 'react'

/** Phones only: the width stance.css stacks a screen at. */
const PHONE = '(max-width: 767px)'
/** Room kept for the "More" button under the panel, with the gap above it. */
const MORE_ROOM = 64
/** The smallest a first block is zoomed to before it is left to the "More" view. */
const MIN_ZOOM = 0.55
/** A zoom chosen within this long of the last one may only go down (see `lastZoom`). */
const ZOOM_BURST_MS = 1500
/** A re-measure within this of the zoom already shown keeps it. */
const ZOOM_KEEP = 0.04
/** More than this many observer-driven measures inside the window is a layout loop: the observers stop. */
const LOOP_MAX_RUNS = 6
const LOOP_WINDOW_MS = 2000

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
    // A zoom changes the width its chart is laid out at, which changes the chart's height, which asks for another zoom (#1415,
    // Sites "spasming" on 360x740 and 375x667: 0.61 / 0.55 / 0.61 ... for ever). A zoom chosen in the last moment only ever
    // goes down, so a burst of re-measures ends at the first zoom that fits; and a burst that goes on is stopped (see `schedule`).
    let lastZoom = 1
    let lastZoomAt = 0

    const reset = () => {
      section.querySelectorAll<HTMLElement | SVGElement>('.fit-hidden').forEach((e) => e.classList.remove('fit-hidden'))
      section.querySelectorAll<HTMLElement | SVGElement>('[data-fit-zoom]').forEach((e) => {
        e.style.removeProperty('zoom')
        e.style.removeProperty('max-height')
        e.removeAttribute('data-fit-zoom')
      })
    }
    /** The panel's blocks, in order: a wrapper with several blocks counts as its blocks. A <figure> (a map with its title,
     *  key and notes) is one block: split, its title could stay while the map itself waited behind "More" (#1349). */
    /** An element the fit can hide or zoom: HTML, or a chart's own <svg> (never the shapes inside one). */
    type Block = HTMLElement | SVGSVGElement
    const isBlock = (k: Element): k is Block => k instanceof HTMLElement || k instanceof SVGSVGElement
    const blocks = (el: Element, room: number, depth = 0): Block[] => {
      const kids = [...el.children].filter((k): k is Block => isBlock(k) && !k.classList.contains('stance-screen-more'))
      return kids.flatMap((k) => {
        const tall = k.getBoundingClientRect().height > room
        const inner = [...k.children].filter((c) => isBlock(c) && c.getBoundingClientRect().height > 0)
        return tall && depth < 3 && inner.length > 1 && !(k instanceof SVGElement) && !k.matches('svg, canvas, ul, ol, dl, table, figure')
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
        if (el instanceof HTMLElement && !el.matches('.stance-card, .stance-head, .stance-nav, .stance-broaden, .story-summary') && el.getBoundingClientRect().height > 0) {
          el.classList.add('fit-hidden')
          hidden = true
        }
      }
      const room = Math.min(barAt, gridAt) - rightAt - MORE_ROOM
      const list = blocks(right, room).filter((b) => b.getBoundingClientRect().height > 0)
      // The panel's first real block (not just a heading over it) always stays, zoomed down when it alone is too tall
      // (never under MIN_ZOOM: past that it stays and the screen scrolls, never an empty panel). Blocks after it are then
      // measured again, after the zoom, and wait behind "More" when they run under the bar.
      const heading = (b: Block) => b.matches('p, h1, h2, h3, h4, h5, h6') && b.getBoundingClientRect().height < 60
      let keep = list.findIndex((b) => !heading(b))
      if (keep < 0) keep = list.length - 1
      const primary = list[keep]
      if (primary) {
        const over = primary.getBoundingClientRect().bottom - top - room
        if (over > 0 && room > 0) {
          const h = primary.getBoundingClientRect().height
          let z = Math.max(MIN_ZOOM, (h - over) / h)
          const now = performance.now()
          if (now - lastZoomAt < ZOOM_BURST_MS) z = Math.min(z, lastZoom)
          // A late re-measure that lands within a few percent of the zoom already shown keeps it: no visible nudge.
          else if (lastZoom < 1 && Math.abs(z - lastZoom) < ZOOM_KEEP) z = lastZoom
          lastZoom = z
          lastZoomAt = now
          // A chart's <svg> is as wide as its column, so zoom leaves its height alone: cap its height instead (its viewBox
          // keeps the drawing whole). Anything else is zoomed.
          if (primary instanceof SVGSVGElement) primary.style.setProperty('max-height', `${Math.floor(h * z)}px`)
          else primary.style.setProperty('zoom', String(Math.floor(z * 100) / 100))
          primary.setAttribute('data-fit-zoom', '')
          hidden = true
        }
      }
      list.forEach((b, i) => {
        if (i <= keep) return
        if (b.getBoundingClientRect().bottom - top > room) {
          b.classList.add('fit-hidden')
          hidden = true
        }
      })
      // Still too tall at the smallest zoom: inside it, keep its first real block and send the rest behind "More" too.
      // A figure is never split (#1349): it stays whole at the smallest zoom and the screen scrolls.
      if (primary && !primary.matches('figure') && primary.getBoundingClientRect().bottom - top > room) {
        const inner = blocks(primary, 0).filter((b) => b !== primary && b.getBoundingClientRect().height > 0)
        const firstReal = inner.findIndex((b) => !heading(b))
        inner.forEach((b, i) => {
          if (i <= firstReal) return
          if (b.getBoundingClientRect().bottom - top > room) {
            b.classList.add('fit-hidden')
            hidden = true
          }
        })
      }
      setHasMore(hidden)
    }
    // A re-measure after our own change lands on the same result and the same size, so the observers settle.
    let runs: number[] = []
    let frozen = false
    const schedule = () => {
      if (frame || frozen) return
      frame = requestAnimationFrame(measure)
    }
    // What the size and content observers ask for: a screen that keeps asking (a layout that never settles) is left as it is.
    const observed = () => {
      const now = performance.now()
      runs = runs.filter((t) => now - t < LOOP_WINDOW_MS)
      runs.push(now)
      if (runs.length > LOOP_MAX_RUNS) {
        frozen = true
        ro?.disconnect()
        mo?.disconnect()
        return
      }
      schedule()
    }
    // A real change of the window starts over.
    const rescheduleAll = () => {
      frozen = false
      runs = []
      if (ro && !frozen) {
        ro.disconnect()
        ro.observe(right)
      }
      if (mo) {
        mo.disconnect()
        mo.observe(right, { childList: true, subtree: true })
      }
      schedule()
    }
    measure()
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(observed) : null
    ro?.observe(right)
    const mo = typeof MutationObserver !== 'undefined' ? new MutationObserver(observed) : null
    mo?.observe(right, { childList: true, subtree: true })
    window.addEventListener('resize', rescheduleAll)
    mq.addEventListener?.('change', rescheduleAll)
    // Late layout (fonts, the screen sliding in): measure again once things settle.
    const lates = [600, 1500, 3000].map((ms) =>
      window.setTimeout(schedule, ms),
    )
    return () => {
      ro?.disconnect()
      mo?.disconnect()
      window.removeEventListener('resize', rescheduleAll)
      mq.removeEventListener?.('change', rescheduleAll)
      lates.forEach((t) => window.clearTimeout(t))
      if (frame) cancelAnimationFrame(frame)
      reset()
    }
  }, [sectionRef, rightRef, active, more])
  return hasMore
}
