import { useEffect, useRef, useState, type RefObject } from 'react'
import { floatingLabel } from '../../utils/floatingNext'

interface Props {
  /** The page (or screen container) to look in. */
  rootRef: RefObject<HTMLElement>
  /** CSS selector of the screen in view inside the root; omitted, the whole root is one screen. */
  screen?: string
  /** Told when the bar appears or goes, so nothing else is drawn over it (the scroll cue). */
  onShownChange?: (shown: boolean) => void
}

interface Item {
  el: HTMLElement
  label: string
  disabled: boolean
  pressed: boolean
}

interface View {
  items: Item[]
  back: HTMLElement | null
}

const ACTIONS = 'button, a[href]'

/** The element a screen marks as its one primary action (a button, a link, or a group of answers), if it is rendered. */
function findPrimary(scope: HTMLElement): HTMLElement | null {
  for (const el of Array.from(scope.querySelectorAll<HTMLElement>('[data-primary]'))) {
    if (el.getClientRects().length > 0) return el
  }
  return null
}

function read(scope: HTMLElement, primary: HTMLElement): View {
  const els = primary.matches(ACTIONS) ? [primary] : Array.from(primary.querySelectorAll<HTMLElement>(ACTIONS))
  const items = els.map((el) => ({
    el,
    label: floatingLabel(el),
    disabled: (el as HTMLButtonElement).disabled === true,
    pressed: el.getAttribute('aria-pressed') === 'true',
  }))
  return { items, back: scope.querySelector<HTMLElement>('.stance-back') }
}

const same = (a: View | null, b: View | null) =>
  a === b ||
  (a != null &&
    b != null &&
    a.back === b.back &&
    a.items.length === b.items.length &&
    a.items.every((x, i) => {
      const y = b.items[i]!
      return x.el === y.el && x.label === y.label && x.disabled === y.disabled && x.pressed === y.pressed
    }))

/**
 * The one obvious next step, always on screen (#915). Every screen marks its primary action with `data-primary`: a button, a
 * link, or the group of answers. While that element is in view nothing is added. When it is not (below the fold, or inside a
 * block that scrolls), a bar pinned to the bottom of the window shows the same action, with a quieter Back beside it when the
 * screen has one. Pressing the bar presses the real control, so there is one behaviour and one accessible name.
 *
 * The bar is for touch and pointer: it is hidden from assistive technology and left out of the tab order, because the real
 * control is still in the page for the keyboard and for screen readers.
 */
export default function FloatingNext({ rootRef, screen, onShownChange }: Props) {
  const [view, setView] = useState<View | null>(null)
  const told = useRef(false)

  useEffect(() => {
    const root = rootRef.current
    if (!root || typeof IntersectionObserver === 'undefined') return
    let primary: HTMLElement | null = null
    let io: IntersectionObserver | null = null
    let inView = true
    let raf = 0

    const publish = () => {
      const scope = (screen ? root.querySelector<HTMLElement>(screen) : root) ?? null
      const next = scope && primary && primary.isConnected && !inView ? read(scope, primary) : null
      setView((prev) => (same(prev, next) ? prev : next))
    }
    const watch = () => {
      raf = 0
      const scope = (screen ? root.querySelector<HTMLElement>(screen) : root) ?? null
      const found = scope ? findPrimary(scope) : null
      if (found !== primary) {
        io?.disconnect()
        io = null
        primary = found
        inView = true
        if (primary) {
          // What sits under the sticky site header and the page's own bar does not count as visible.
          const header = document.querySelector<HTMLElement>('.site-header')
          const top = root.querySelector<HTMLElement>('.stance-top')
          const off = (header?.offsetHeight ?? 0) + (top?.offsetHeight ?? 0)
          io = new IntersectionObserver(
            (entries) => {
              const e = entries[entries.length - 1]
              if (!e) return
              inView = e.intersectionRatio >= 0.75
              publish()
            },
            { threshold: [0, 0.25, 0.5, 0.75, 1], rootMargin: `-${off}px 0px 0px 0px` },
          )
          io.observe(primary)
        }
      }
      publish()
    }
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(watch)
    }
    const mo = new MutationObserver(schedule)
    mo.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-primary', 'disabled', 'aria-pressed', 'data-state', 'hidden'] })
    window.addEventListener('resize', schedule)
    watch()
    return () => {
      if (raf) cancelAnimationFrame(raf)
      mo.disconnect()
      io?.disconnect()
      window.removeEventListener('resize', schedule)
    }
  }, [rootRef, screen])

  const shown = view != null && view.items.length > 0
  useEffect(() => {
    if (told.current !== shown) {
      told.current = shown
      onShownChange?.(shown)
    }
  }, [shown, onShownChange])
  useEffect(() => () => onShownChange?.(false), [onShownChange])

  if (!shown || !view) return null
  const many = view.items.length > 1
  return (
    <div className={`stance-float${many ? ' is-many' : ''}`} aria-hidden="true" data-testid="floating-next">
      {view.back && (
        <button type="button" tabIndex={-1} className="stance-float-back" onClick={() => view.back?.click()}>
          ← Back
        </button>
      )}
      {view.items.map((it, i) => (
        <button
          key={i}
          type="button"
          tabIndex={-1}
          className={`stance-float-btn${it.pressed ? ' is-pressed' : ''}`}
          disabled={it.disabled}
          onClick={() => it.el.click()}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}
