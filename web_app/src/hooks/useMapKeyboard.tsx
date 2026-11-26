import { useId, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from 'react'

/** The key a map's arrow keys move to (#1146): next/previous in `keys`, wrapping; Home/End go to the ends. */
export function nextMapKey<K>(keys: readonly K[], current: K | null, key: string): K | null {
  if (!keys.length) return null
  const i = current == null ? -1 : keys.indexOf(current)
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      return keys[i < 0 ? 0 : (i + 1) % keys.length]!
    case 'ArrowLeft':
    case 'ArrowUp':
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
 */
export function useMapKeyboard<K>({ keys, active, setActive, initial, describe, onActivate, noun }: Options<K>) {
  const hintId = useId()
  const [said, setSaid] = useState('')
  const move = (k: K | null) => {
    setActive(k)
    setSaid(k == null ? '' : describe(k))
  }
  const onKeyDown = (e: KeyboardEvent<Element>) => {
    if (e.key === 'Escape') {
      if (active != null) {
        e.preventDefault()
        move(null)
      }
      return
    }
    if ((e.key === 'Enter' || e.key === ' ') && active != null && onActivate) {
      e.preventDefault()
      onActivate(active)
      return
    }
    const k = nextMapKey(keys, active, e.key)
    if (k != null) {
      e.preventDefault()
      move(k)
    }
  }
  const onFocus = () => {
    if (active == null && keys.length) move(initial != null && keys.includes(initial) ? initial : keys[0]!)
  }
  const svgProps = {
    tabIndex: 0,
    role: 'group' as const,
    'aria-roledescription': 'map',
    'aria-describedby': hintId,
    'data-map-keys': '',
    onKeyDown,
    onFocus,
  }
  // Leaving the map and its card (not moving between them) hides the card, as leaving with the mouse does.
  const stageProps = {
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setActive(null)
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
  return { svgProps, stageProps, sr }
}
