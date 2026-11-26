import { useEffect, useState } from 'react'
import { cueWord } from '../../utils/scrollCue'
import '../../styles/scroll-cue.css'

interface Props {
  /** The screen in view has a next one. */
  show: boolean
  /** Where the cue goes, in words ("Concerns"); it is the button's accessible name. */
  nextLabel: string
  onNext: () => void
  /** How long the reader must be still before the cue appears. */
  idleMs?: number
}

function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(pointer: coarse)')
    const on = () => setCoarse(mq.matches)
    on()
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return coarse
}

/**
 * The invitation to move on (#904): a small button at the bottom centre of the window with a chevron that travels downward on
 * a loop. It appears once the reader has been still for a moment, hides while the page moves, and goes to the next screen when
 * pressed. The animation is CSS and is switched off under `prefers-reduced-motion`; the cue itself still shows.
 */
export default function ScrollCue({ show, nextLabel, onNext, idleMs = 2000 }: Props) {
  const coarse = useCoarsePointer()
  const [idle, setIdle] = useState(false)
  useEffect(() => {
    if (!show) {
      setIdle(false)
      return
    }
    let timer = window.setTimeout(() => setIdle(true), idleMs)
    const busy = () => {
      setIdle(false)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setIdle(true), idleMs)
    }
    const opts = { passive: true } as const
    window.addEventListener('scroll', busy, opts)
    window.addEventListener('wheel', busy, opts)
    window.addEventListener('touchmove', busy, opts)
    window.addEventListener('keydown', busy)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('scroll', busy)
      window.removeEventListener('wheel', busy)
      window.removeEventListener('touchmove', busy)
      window.removeEventListener('keydown', busy)
    }
  }, [show, idleMs, nextLabel])

  if (!show) return null
  return (
    <button
      type="button"
      className={`scroll-cue${idle ? ' is-on' : ''}`}
      aria-label={`Next: ${nextLabel}`}
      aria-hidden={idle ? undefined : true}
      tabIndex={idle ? 0 : -1}
      onClick={onNext}
    >
      <span className="scroll-cue-word">{cueWord(coarse)}</span>
      <svg className="scroll-cue-chevrons" viewBox="0 0 24 28" width="24" height="28" aria-hidden="true" focusable="false">
        <path className="scroll-cue-c1" d="M5 6l7 7 7-7" />
        <path className="scroll-cue-c2" d="M5 15l7 7 7-7" />
      </svg>
    </button>
  )
}
