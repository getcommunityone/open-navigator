import { useEffect, useRef } from 'react'
import { FIG_NO } from './data'
import { SECTIONS, type SectionId } from './types'

/**
 * Sticky band under the Data explorer tabs: the section numbers (the one in view is marked with aria-current), a scroll
 * progress line along its bottom edge, and click / keyboard jumps. It is a `nav` of real links.
 */
export default function SectionBand({
  active,
  onJump,
  rootRef,
  reduced,
}: {
  active: SectionId
  onJump: (id: SectionId) => void
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
  return (
    <nav className="folio-band" aria-label="Matrix map sections">
      <span className="folio-band-label">Section</span>
      <ol className="folio-band-list">
        {SECTIONS.map((s, i) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className="folio-band-link"
              aria-current={active === s.id ? 'true' : undefined}
              aria-label={`Section ${i + 1}: ${s.name}`}
              title={s.name}
              onClick={(e) => {
                e.preventDefault()
                onJump(s.id)
              }}
            >
              {FIG_NO(i)}
            </a>
          </li>
        ))}
      </ol>
      <span className="folio-band-name" aria-hidden="true">
        {SECTIONS.find((s) => s.id === active)?.name}
      </span>
      <span className="folio-band-progress" aria-hidden="true">
        <span ref={bar} />
      </span>
    </nav>
  )
}
