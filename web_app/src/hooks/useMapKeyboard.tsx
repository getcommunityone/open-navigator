import { useEffect, useId, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from 'react'

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

/**
 * True when a press landed outside the map and its card (#1229): on a phone nothing may depend on hover, so a tap
 * anywhere else on the page closes the card a tap opened, the way moving the mouse away closes it on a desktop.
 */
export function pressedOutside(stage: Pick<Node, 'contains'> | null, target: EventTarget | null): boolean {
  if (!stage || !target) return false
  return !stage.contains(target as Node)
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
    onKeyDown,
    onFocus,
    onPointerDown,
  }
  // A tap (or click) outside the map and its card closes the card (#1229). Not left to blur: a tap on a page's plain
  // text moves no focus on iOS, and the svg may never have had focus.
  const stageRef = useRef<HTMLDivElement>(null)
  const shown = active != null
  useEffect(() => {
    if (!shown) return
    const onDown = (e: PointerEvent) => {
      if (pressedOutside(stageRef.current, e.target)) move(null)
    }
    document.addEventListener('pointerdown', onDown, true)
    return () => document.removeEventListener('pointerdown', onDown, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- move only wraps setActive; re-subscribing on every render is waste.
  }, [shown])
  // Leaving the map and its card (not moving between them) hides the card, as leaving with the mouse does.
  const stageProps = {
    ref: stageRef,
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
  /** Closes the card: the card's own close control (#1229), so a phone reader never needs hover to dismiss it. */
  const close = () => move(null)
  return { svgProps, stageProps, sr, close }
}

/**
 * The close control on a map card (#1229): a real button, 44px tall, so a tap closes the card on a phone. Inline styles so
 * it looks the same on the home page and in the stories.
 */
export function MapCardClose({ onClose, label = 'Close' }: { onClose: () => void; label?: string }) {
  return (
    <button
      type="button"
      className="map-card-close"
      onClick={onClose}
      style={{
        display: 'block',
        width: '100%',
        margin: '8px 0 0',
        minHeight: 44,
        padding: '10px 16px',
        boxSizing: 'border-box',
        border: '1px solid #d6d3d1',
        borderRadius: 999,
        background: '#fff',
        color: '#44403c',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}
