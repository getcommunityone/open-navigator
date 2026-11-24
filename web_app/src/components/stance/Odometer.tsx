import { useEffect, useRef } from 'react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface Props {
  /** The real text to show, for example "1,204" or "03". It is always in the DOM in its final form. */
  text: string
  /** Roll the characters in (once on first play, then only the characters that changed). Off: static text. */
  play?: boolean
  className?: string
}

const EASING = 'cubic-bezier(0.23, 1, 0.32, 1)'

/**
 * Rolling digits after the reference's odometer: each character sits in a slot and slides up into place; only characters
 * that differ from what was shown before roll. It rolls only to the real value, never through made-up numbers, and does
 * nothing under reduced motion. Screen readers get the plain text.
 */
export default function Odometer({ text, play = true, className }: Props) {
  const reduced = usePrefersReducedMotion()
  const root = useRef<HTMLSpanElement>(null)
  const shown = useRef<string | null>(null)

  useEffect(() => {
    if (!play) return
    const prev = shown.current
    shown.current = text
    if (reduced || typeof Element === 'undefined' || !('animate' in Element.prototype)) return
    const chars = root.current?.querySelectorAll<HTMLElement>('[data-ch]')
    chars?.forEach((el, i) => {
      if (prev != null && prev[i] === text[i] && prev.length === text.length) return
      el.animate(
        [
          { transform: 'translateY(105%)', opacity: 0 },
          { transform: 'translateY(0)', opacity: 1 },
        ],
        { duration: 520, delay: i * 45, easing: EASING, fill: 'backwards' },
      )
    })
  }, [text, play, reduced])

  return (
    <span className={`stance-odo${className ? ` ${className}` : ''}`} ref={root}>
      <span className="folio-sr-only">{text}</span>
      <span aria-hidden="true" className="stance-odo-vis">
        {Array.from(text).map((c, i) => (
          <span className="stance-odo-slot" key={i}>
            <span data-ch="">{c}</span>
          </span>
        ))}
      </span>
    </span>
  )
}
