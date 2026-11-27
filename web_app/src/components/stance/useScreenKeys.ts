import { useEffect, useRef } from 'react'

interface Options {
  /** Move to the next screen. */
  next: () => void
  /** Move to the previous screen. */
  prev: () => void
  first: () => void
  last: () => void
  /** False while a popover or dialog owns the keyboard. */
  enabled?: boolean
}

/** Where the keyboard belongs to the control itself, not to the page. */
const OWN_KEYS = 'input, select, textarea, [contenteditable="true"], table, [data-keys-own], [role="listbox"], [role="menu"]'

/**
 * Keys that move between screens, shared by the challenge and the story: PageDown / Enter / Space / arrow down / arrow right go on,
 * PageUp / Shift+Space / arrow up / arrow left go back, Home and End jump to the ends. Nothing happens while focus is in an
 * input, select, table or a figure that scrolls on its own, and Space and Enter leave a focused button or link to press it.
 * Wheel and touch are untouched: this never traps the reader.
 */
export function useScreenKeys(opts: Options) {
  const o = useRef(opts)
  o.current = opts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (o.current.enabled === false) return
      if (t && t !== document.body && t.closest?.(OWN_KEYS)) return
      // A modal sheet or dialog owns the keyboard: the story behind it stays on its screen.
      if (t?.closest?.('[role="dialog"]') || document.querySelector('[role="dialog"][aria-modal="true"]')) return
      const scrollsInside = t?.closest?.('[data-lenis-prevent]') != null
      const onControl = t != null && (t.tagName === 'BUTTON' || t.tagName === 'A' || t.closest?.('summary') != null)
      let act: (() => void) | null = null
      switch (e.key) {
        case 'PageDown':
          act = o.current.next
          break
        case 'Enter':
          // A focused button, link or summary keeps Enter (it presses it); anywhere else Enter goes on, like Next.
          if (onControl || e.shiftKey) return
          act = o.current.next
          break
        case 'PageUp':
          act = o.current.prev
          break
        case ' ':
          // A focused button or link keeps plain Space (it presses it); Shift+Space still goes back.
          if (onControl && !e.shiftKey) return
          act = e.shiftKey ? o.current.prev : o.current.next
          break
        case 'ArrowDown':
          if (scrollsInside) return
          act = o.current.next
          break
        case 'ArrowUp':
          if (scrollsInside) return
          act = o.current.prev
          break
        case 'ArrowRight':
          act = o.current.next
          break
        case 'ArrowLeft':
          act = o.current.prev
          break
        case 'Home':
          if (scrollsInside) return
          act = o.current.first
          break
        case 'End':
          if (scrollsInside) return
          act = o.current.last
          break
        default:
          return
      }
      e.preventDefault()
      act()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
