import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { nextMapKey, pressedOutside, useMapKeyboard, westToEast } from './useMapKeyboard'

describe('nextMapKey (#1146)', () => {
  const keys = ['WA', 'TX', 'NY']
  it('moves left and right, wrapping', () => {
    expect(nextMapKey(keys, 'WA', 'ArrowRight')).toBe('TX')
    expect(nextMapKey(keys, 'NY', 'ArrowRight')).toBe('WA')
    expect(nextMapKey(keys, 'WA', 'ArrowLeft')).toBe('NY')
  })
  it('starts at an end when nothing is shown, and Home/End jump to the ends', () => {
    expect(nextMapKey(keys, null, 'ArrowRight')).toBe('WA')
    expect(nextMapKey(keys, null, 'ArrowLeft')).toBe('NY')
    expect(nextMapKey(keys, 'TX', 'Home')).toBe('WA')
    expect(nextMapKey(keys, 'TX', 'End')).toBe('NY')
  })
  it('leaves Up/Down to the page so a focused map still scrolls', () => {
    expect(nextMapKey(keys, 'TX', 'ArrowUp')).toBeNull()
    expect(nextMapKey(keys, 'TX', 'ArrowDown')).toBeNull()
    expect(nextMapKey([], null, 'ArrowRight')).toBeNull()
  })
})

describe('westToEast', () => {
  it('orders areas by the centre of their dots', () => {
    const dots = [{ x: 9, y: 0 }, { x: 1, y: 0 }, { x: 3, y: 0 }, { x: 5, y: 0 }]
    const ids = ['NY', 'WA', 'WA', null]
    expect(westToEast(dots, (i) => ids[i] ?? null)).toEqual(['WA', 'NY'])
  })
})

describe('useMapKeyboard focus', () => {
  /** One render of the hook, its map props kept for the test to call. */
  const setup = () => {
    const setActive = vi.fn()
    let props: { onFocus: () => void; onPointerDown: () => void } | null = null
    function Probe() {
      props = useMapKeyboard({ keys: ['WA', 'AL', 'NY'], active: null, setActive, initial: 'AL', describe: (k) => k, noun: 'state' }).svgProps
      return null
    }
    renderToStaticMarkup(<Probe />)
    return { setActive, props: props! }
  }
  it('starts keyboard focus on the page’s own area', () => {
    const { setActive, props } = setup()
    props.onFocus()
    expect(setActive).toHaveBeenCalledWith('AL')
  })
  it('does not pick the page’s area when a tap or click focuses the map (the phone button bug)', () => {
    const { setActive, props } = setup()
    props.onPointerDown()
    props.onFocus()
    expect(setActive).not.toHaveBeenCalled()
    // The next keyboard focus still starts on it.
    props.onFocus()
    expect(setActive).toHaveBeenCalledWith('AL')
  })
  it('a press that focused nothing does not skip a later keyboard focus', () => {
    vi.useFakeTimers()
    try {
      const { setActive, props } = setup()
      props.onPointerDown()
      vi.advanceTimersByTime(5000)
      props.onFocus()
      expect(setActive).toHaveBeenCalledWith('AL')
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('pressedOutside (#1229: a tap outside closes the card on a phone)', () => {
  const inside = { id: 'box' } as unknown as EventTarget
  const outside = { id: 'page' } as unknown as EventTarget
  const stage = { contains: (n: Node | null) => (n as unknown) === inside }
  it('is true for a press anywhere but the map and its card', () => {
    expect(pressedOutside(stage, outside)).toBe(true)
  })
  it('is false for a press on the map or its card (the next state, the card buttons)', () => {
    expect(pressedOutside(stage, inside)).toBe(false)
  })
  it('is false with no stage or no target', () => {
    expect(pressedOutside(null, outside)).toBe(false)
    expect(pressedOutside(stage, null)).toBe(false)
  })
})

describe('useMapKeyboard close (#1229)', () => {
  it('returns a close that hides the card', () => {
    const setActive = vi.fn()
    let close: (() => void) | null = null
    function Probe() {
      close = useMapKeyboard({ keys: ['WA'], active: 'WA', setActive, describe: (k) => k, noun: 'state' }).close
      return null
    }
    renderToStaticMarkup(<Probe />)
    close!()
    expect(setActive).toHaveBeenCalledWith(null)
  })
})
