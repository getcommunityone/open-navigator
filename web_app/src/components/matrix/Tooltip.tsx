import { useCallback, useState, type PointerEvent as RPointerEvent } from 'react'

export interface TipInfo {
  cat: string
  val: string
  sub?: string
  /** A small preview image (a meeting recording's thumbnail, #972); loaded only when the tooltip shows. */
  thumb?: string
}
interface TipState extends TipInfo {
  x: number
  y: number
}
type Source = { clientX: number; clientY: number } | Element | null

/** The reference's tooltip: category, big value, sub line. Follows the pointer; anchors above the element on keyboard focus. */
export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null)
  const show = useCallback((info: TipInfo, src?: Source) => {
    let x = 16
    let y = 56
    // A tooltip with a thumbnail is about 100px taller: keep it on screen and clear of the element.
    const extra = info.thumb ? 100 : 0
    if (src && 'clientX' in src && typeof src.clientX === 'number') {
      x = src.clientX + 16
      y = src.clientY + 16
      if (x > window.innerWidth - 260) x = src.clientX - 256
      if (y > window.innerHeight - 110 - extra) y = src.clientY - 100 - extra
    } else if (src && 'getBoundingClientRect' in src) {
      const r = src.getBoundingClientRect()
      x = Math.min(window.innerWidth - 256, Math.max(12, r.left + r.width / 2 - 120))
      y = r.top - 90 - extra < 12 ? r.bottom + 10 : r.top - 90 - extra
    }
    setTip({ ...info, x: Math.max(12, x), y: Math.max(48, y) })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  return {
    tip,
    show,
    hide,
    /** Spread onto an SVG/HTML element: shows on pointer move and focus, hides on leave and blur. */
    bind: (info: TipInfo) => ({
      onPointerEnter: (e: RPointerEvent) => show(info, e),
      onPointerMove: (e: RPointerEvent) => show(info, e),
      onPointerLeave: hide,
      onFocus: (e: { currentTarget: Element }) => show(info, e.currentTarget),
      onBlur: hide,
    }),
  }
}

export function Tooltip({ tip }: { tip: (TipInfo & { x: number; y: number }) | null }) {
  if (!tip) return null
  return (
    <div className="folio-tt" style={{ transform: `translate3d(${Math.round(tip.x)}px, ${Math.round(tip.y)}px, 0)` }} aria-hidden="true">
      {tip.thumb ? <img className="folio-tt-thumb" src={tip.thumb} alt="" width={160} height={90} loading="lazy" decoding="async" /> : null}
      <div className="folio-tt-cat">{tip.cat}</div>
      <div className="folio-tt-val">{tip.val}</div>
      {tip.sub ? <div className="folio-tt-sub">{tip.sub}</div> : null}
    </div>
  )
}
