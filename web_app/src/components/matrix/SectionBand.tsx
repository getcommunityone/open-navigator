import { useEffect, useRef } from 'react'
import { CHAPTERS, SCREENS, adjacentScreens, chapterDomId, screenLabel, type LabelInput } from '../../utils/matrixStory'

/**
 * The slim story bar under the site header: the five chapter phrases as links, the one in view marked with `aria-current`,
 * and a thin progress line along its bottom edge. Under the current chapter, one small dot per screen (no numbers; each
 * has the screen's plain name as its accessible name). On a phone only the current phrase and the progress line show; the
 * Continue and Back controls do the paging there. It is a `nav` of real links. `pos` is the DOM id in view.
 */
export default function SectionBand({
  pos,
  onJump,
  rootRef,
  reduced,
  labels,
  selection,
  onTop,
  onChange,
}: {
  pos: string
  onJump: (domId: string) => void
  /** The element whose height the progress line measures (the sections wrapper). */
  rootRef: React.RefObject<HTMLElement>
  reduced: boolean
  labels: LabelInput
  /** The measure and the place in view, in words, for the "change" link. */
  selection: { measure: string; place: string }
  /** Back to the very top of the page and the main menu. */
  onTop: () => void
  /** Back to the heading's blanks so the reader can change the measure. */
  onChange: () => void
}) {
  const bar = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const root = rootRef.current
      if (!root || !bar.current) return
      const r = root.getBoundingClientRect()
      const span = r.height - window.innerHeight * 0.6
      const p = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 0
      bar.current.style.transform = `scaleX(${p.toFixed(4)})`
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [rootRef, reduced])
  const here = adjacentScreens(pos)
  const screen = SCREENS[Math.max(0, here.index)]!
  const chapter = CHAPTERS.find((c) => c.id === screen.chapter) ?? CHAPTERS[0]!
  return (
    <nav className="folio-band" aria-label="Parts of this analysis">
      <button type="button" className="folio-band-top" aria-label="Back to the top and the main menu" onClick={onTop}>
        <span aria-hidden="true">↑</span> Top
      </button>
      <ol className="folio-band-list">
        {CHAPTERS.map((c) => (
          <li key={c.id} className="folio-band-chapter">
            <a
              href={`#${chapterDomId(c.id)}`}
              className="folio-band-chap"
              aria-current={chapter.id === c.id ? 'true' : undefined}
              onClick={(e) => {
                e.preventDefault()
                onJump(chapterDomId(c.id))
              }}
            >
              {c.bandLabel}
            </a>
            {chapter.id === c.id && (
              <ol className="folio-band-sub" aria-label={`Screens in ${c.bandLabel}`}>
                {SCREENS.filter((s) => s.chapter === c.id).map((s) => (
                  <li key={s.domId}>
                    <a
                      href={`#${s.domId}`}
                      className="folio-band-dot"
                      aria-current={screen.domId === s.domId ? 'true' : undefined}
                      aria-label={screenLabel(s.section, labels)}
                      title={screenLabel(s.section, labels)}
                      onClick={(e) => {
                        e.preventDefault()
                        onJump(s.domId)
                      }}
                    >
                      <span aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ol>
      <span className="folio-band-name" aria-hidden="true">
        {chapter.bandLabel}
      </span>
      <button type="button" className="folio-band-select" onClick={onChange} aria-label={`Showing ${selection.measure} in ${selection.place}. Change`}>
        <span className="folio-band-measure">{selection.measure}</span>
        <span className="folio-band-place"> · {selection.place}</span>
        <span className="folio-band-change">change</span>
      </button>
      <span className="folio-band-progress" aria-hidden="true">
        <span ref={bar} />
      </span>
    </nav>
  )
}
