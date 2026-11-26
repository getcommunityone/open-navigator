import { Fragment, useEffect, useLayoutEffect, useRef, useState, type ElementType } from 'react'
import { useTitleShown } from './hooks'

/**
 * Split `text` into the lines the browser actually sets it in: lay the words out in a hidden copy that has the heading's own
 * width and type, then group them by their top edge.
 */
function measureLines(box: HTMLElement): string[] | null {
  const words = Array.from(box.querySelectorAll<HTMLElement>('[data-w]'))
  if (!words.length) return null
  const lines: string[][] = []
  let top = Number.NaN
  for (const w of words) {
    const t = Math.round(w.offsetTop)
    if (lines.length === 0 || Math.abs(t - top) > 2) {
      lines.push([])
      top = t
    }
    lines[lines.length - 1]!.push(w.textContent ?? '')
  }
  return lines.map((l) => l.join(' '))
}

interface Props {
  /** Heading level: chapter cards use h2, section headlines h3 (the page's single h1 is the Data explorer title). */
  as: 'h2' | 'h3'
  id: string
  /** Small mono line above the title; fades in first. */
  eyebrow: string
  /** The title. It is split into the lines the browser sets it in; each line rises from behind its own mask. */
  text: string
  variant: 'section' | 'chapter'
  /** Draw a rule under the title as it enters (chapter cards). */
  rule?: boolean
}

/**
 * The reference's headline entrance (`.headline-h2` > `.line` > `.line-inner`): every line sits in an overflow-hidden mask and
 * rises from 105% to 0 over the 900 ms `--d-4` with the `--ease-out` curve, line 2 after 80 ms and line 3 after 160 ms, the
 * eyebrow fading first. It plays once, when the block first enters view. Later text changes (a filter) swap the words in
 * place without replaying it, and a resize re-measures the lines without replaying it too. Under prefers-reduced-motion the
 * title is simply there (folio.css).
 *
 * The heading's full text is in the accessibility tree through a visually hidden copy; the masked lines are `aria-hidden`.
 */
export default function TitleBlock({ as, id, eyebrow, text, variant, rule }: Props) {
  const Heading = as as ElementType
  const block = useRef<HTMLDivElement>(null)
  const head = useRef<HTMLElement>(null)
  const measure = useRef<HTMLSpanElement>(null)
  const shown = useTitleShown(block)
  const [lines, setLines] = useState<string[]>([text])
  const width = useRef(0)

  const relayout = () => {
    const m = measure.current
    if (!m) return
    const next = measureLines(m)
    if (next) setLines((cur) => (cur.length === next.length && cur.every((l, i) => l === next[i]) ? cur : next))
  }
  // Re-measure after every render (cheap: a dozen words), before paint, so the first frame already has real lines and a
  // changed headline never shows one wrong frame. Equal lines leave the state alone.
  useLayoutEffect(relayout)
  useEffect(() => {
    const el = head.current
    if (!el) return
    width.current = Math.round(el.getBoundingClientRect().width)
    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => {
        const w = Math.round(el.getBoundingClientRect().width)
        if (w !== width.current) {
          width.current = w
          relayout()
        }
      })
      ro.observe(el)
    }
    // The web font arrives after the first paint and changes the line breaks.
    let live = true
    void document.fonts?.ready.then(() => live && relayout())
    const onFont = () => relayout()
    document.fonts?.addEventListener?.('loadingdone', onFont)
    return () => {
      live = false
      ro?.disconnect()
      document.fonts?.removeEventListener?.('loadingdone', onFont)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const words = text.split(' ').filter(Boolean)
  return (
    <div ref={block} className={`folio-title folio-title-${variant}${shown ? ' is-shown' : ''}`}>
      <p className="folio-eyebrow folio-eyebrow-anim">{eyebrow}</p>
      <Heading ref={head} className={variant === 'chapter' ? 'folio-chapter-title' : 'folio-headline'} id={id} tabIndex={-1}>
        <span className="folio-sr-only">{text}</span>
        <span className="folio-lines" aria-hidden="true">
          {lines.map((line, i) => (
            <span className="folio-line" key={i}>
              <span className="folio-line-inner">{line}</span>
            </span>
          ))}
        </span>
        <span className="folio-measure" aria-hidden="true" ref={measure}>
          {words.map((w, i) => (
            <Fragment key={i}>
              <span data-w="">{w}</span>
              {' '}
            </Fragment>
          ))}
        </span>
      </Heading>
      {rule && <hr className="folio-rule folio-rule-draw" />}
    </div>
  )
}
