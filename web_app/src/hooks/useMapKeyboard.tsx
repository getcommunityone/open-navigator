import { useId, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from 'react'

/** The key a map's arrow keys move to (#1146): next/previous in `keys`, wrapping; Home/End go to the ends. */
export function nextMapKey<K>(keys: readonly K[], current: K | null, key: string): K | null {
  if (!keys.length) return null
  const i = current == null ? -1 : keys.indexOf(current)
  switch (key) {
    // Up/Down are left to the page, so a focused map doesn't stop keyboard scrolling.
    case 'ArrowRight':
      return keys[i < 0 ? 0 : (i + 1) % keys.length]!
    case 'ArrowLeft':
      return keys[i < 0 ? keys.length - 1 : (i - 1 + keys.length) % keys.length]!
    case 'Home':
      return keys[0]!
    case 'End':
      return keys[keys.length - 1]!
    default:
      return null
  }
}

/** Area ids ordered west to east by the centre of their dots (then north to south), for the arrow keys. */
export function westToEast<K>(dots: readonly { x: number; y: number }[], idOf: (i: number) => K | null): K[] {
  const sums = new Map<K, { x: number; y: number; n: number }>()
  dots.forEach((d, i) => {
    const id = idOf(i)
    if (id == null) return
    const s = sums.get(id) ?? { x: 0, y: 0, n: 0 }
    s.x += d.x
    s.y += d.y
    s.n += 1
    sums.set(id, s)
  })
  return [...sums]
    .map(([id, s]) => ({ id, x: s.x / s.n, y: s.y / s.n }))
    .sort((a, b) => a.x - b.x || a.y - b.y)
    .map((a) => a.id)
}

/** A focus this soon after a press on the map came from the press. */
const POINTER_FOCUS_MS = 800

interface Options<K> {
  /** The areas the arrow keys move between, in order. */
  keys: readonly K[]
  /** The area shown now (the hovered or focused one), or null. */
  active: K | null
  setActive: (key: K | null) => void
  /** The area focus starts on (the page's scope), else the first. */
  initial?: K | null
  /** What a screen reader hears when the arrows reach an area. */
  describe: (key: K) => string
  /** Enter or Space on an area (open its story); none → the keys only move. */
  onActivate?: (key: K) => void
  /** "state", "county": for the hint. */
  noun: string
}

/**
 * Keyboard and screen-reader support for the story box maps (#1146): the map is one tab stop, the arrow keys move between its
 * areas (showing the quote card as hover does), Enter opens the area's story, Escape hides the card. Each move is announced
 * politely. Spread `svgProps` on the map's svg, `stageProps` on the element holding the svg and its card, and render `sr`.
 * `keyed` is true while the area shown came from the keys; call `pointed()` when the mouse picks one. The hover card plays
 * its recording on its own only for the mouse, never from keyboard focus (#1277).
 */
export function useMapKeyboard<K>({ keys, active, setActive, initial, describe, onActivate, noun }: Options<K>) {
  const hintId = useId()
  const [said, setSaid] = useState('')
  const [keyed, setKeyed] = useState(false)
  const move = (k: K | null) => {
    setKeyed(k != null)
    setActive(k)
    setSaid(k == null ? '' : describe(k))
  }
  const onKeyDown = (e: KeyboardEvent<Element>) => {
    if (e.key === 'Escape') {
      if (active != null) {
        // Hides the card only: the story's own Escape (close the story, #1234) must not also fire.
        e.preventDefault()
        e.stopPropagation()
        move(null)
      }
      return
    }
    if ((e.key === 'Enter' || e.key === ' ') && active != null) {
      // Always consumed while an area is shown, so a map without a story to open doesn't page the story screen instead.
      e.preventDefault()
      onActivate?.(active)
      return
    }
    const k = nextMapKey(keys, active, e.key)
    if (k != null) {
      e.preventDefault()
      move(k)
    }
  }
  // A tap or click also focuses the map (it is a tab stop). That focus must not pick the starting area: on a phone it
  // showed the page's own state's card over the box the reader tapped, so its "Open the … story" button led back to the
  // page they were on. Only keyboard focus starts on `initial`; a pointer shows what it lands on.
  // A timestamp, not a flag: a press on an already-focused map fires no focus, and a flag left set would skip the next
  // keyboard focus.
  const pointerAt = useRef(0)
  const onPointerDown = () => {
    pointerAt.current = Date.now()
  }
  const onFocus = () => {
    const byPointer = Date.now() - pointerAt.current < POINTER_FOCUS_MS
    pointerAt.current = 0
    if (byPointer) return
    if (active == null && keys.length) move(initial != null && keys.includes(initial) ? initial : keys[0]!)
  }
  const svgProps = {
    tabIndex: 0,
    role: 'group' as const,
    'aria-roledescription': 'map',
    'aria-describedby': hintId,
    'data-map-keys': '',
    // A shown area: Escape hides its card first, and the story's Escape (StoryClose) leaves it alone.
    'data-map-active': active != null ? '' : undefined,
    onKeyDown,
    onFocus,
    onPointerDown,
  }
  // Leaving the map and its card (not moving between them) hides the card, as leaving with the mouse does.
  const stageProps = {
    onBlur: (e: FocusEvent<HTMLElement>) => {
      const to = e.relatedTarget as Element | null
      // The hover card may sit outside the stage (the home page's text column, #1277): moving into it is not leaving.
      if (!e.currentTarget.contains(to) && !to?.closest?.('.map-hover-card')) {
        setKeyed(false)
        setActive(null)
      }
    },
  }
  const sr: ReactNode = (
    <>
      <span id={hintId} className="sr-only">
        {`Use the arrow keys to move between each ${noun}${onActivate ? `, Enter to open its story` : ''}, Escape to hide the quote.`}
      </span>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {said}
      </span>
    </>
  )
  /** The mouse picked the area shown: the hover card may play its recording (#1277). */
  const pointed = () => {
    if (keyed) setKeyed(false)
  }
  return { svgProps, stageProps, sr, keyed, pointed }
}
