import { useEffect, useRef } from 'react'
import { FIG_NO } from './data'
import { CHAPTERS, chapterDomId, chapterOfSection } from '../../utils/matrixStory'
import { SECTIONS } from './types'


/**
 * Sticky band under the Data explorer tabs: the five chapters (short labels) with the section numbers under each, the chapter
 * and the section in view marked with aria-current, a scroll progress line along its bottom edge, and click / keyboard jumps.
 * It is a `nav` of real links. `pos` is the DOM id in view: a chapter card (`chapter-<id>`) or a section id.
 */
export default function SectionBand({
  pos,
  onJump,
  rootRef,
  reduced,
}: {
  pos: string
  onJump: (domId: string) => void
  /** The element whose height the progress line measures (the sections wrapper). */
  rootRef: React.RefObject<HTMLElement>
  reduced: boolean
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
  const atChapter = CHAPTERS.find((c) => chapterDomId(c.id) === pos) ?? null
  const section = SECTIONS.find((s) => s.id === pos) ?? null
  const chapter = atChapter ?? (section ? chapterOfSection(section.id) : CHAPTERS[0]!)
  return (
    <nav className="folio-band" aria-label="Matrix map chapters and sections">
      <span className="folio-band-label">Chapter</span>
      <ol className="folio-band-list">
        {CHAPTERS.map((c, ci) => (
          <li key={c.id} className="folio-band-chapter">
            <a
              href={`#${chapterDomId(c.id)}`}
              className="folio-band-chap"
              aria-current={chapter.id === c.id ? 'true' : undefined}
              aria-label={`Chapter ${ci + 1}: ${c.meeting}, ${c.title}`}
              title={`${c.meeting}: ${c.blurb}`}
              onClick={(e) => {
                e.preventDefault()
                onJump(chapterDomId(c.id))
              }}
            >
              {c.short}
            </a>
            <ol className="folio-band-sub">
              {c.sections.map((id) => {
                const i = SECTIONS.findIndex((s) => s.id === id)
                return (
                  <li key={id}>
                    <a
                      href={`#${id}`}
                      className="folio-band-link"
                      aria-current={pos === id ? 'true' : undefined}
                      aria-label={`Section ${i + 1}: ${SECTIONS[i]!.name}`}
                      title={SECTIONS[i]!.name}
                      onClick={(e) => {
                        e.preventDefault()
                        onJump(id)
                      }}
                    >
                      {FIG_NO(i)}
                    </a>
                  </li>
                )
              })}
            </ol>
          </li>
        ))}
      </ol>
      <span className="folio-band-name" aria-hidden="true">
        {chapter.meeting}
        {section ? ` · ${section.name}` : ''}
      </span>
      <span className="folio-band-progress" aria-hidden="true">
        <span ref={bar} />
      </span>
    </nav>
  )
}
