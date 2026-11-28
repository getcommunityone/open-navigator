import { memo } from 'react'

interface Props {
  /** The county or state the box belongs to (what a hover or a pick acts on). */
  id: string
  /** The box's position in the grid. */
  i: number
  dataState: string | undefined
  x: number
  y: number
  size: number
  fill: string
  opacity: number
  active: boolean
  pointer: boolean
  hoverable: boolean
  onEnter: (id: string, i: number) => void
  onPick: (id: string) => void
}

/**
 * One box of a unit-box map (#1458). A county map draws up to ~1,500 and the national one 2,240, and a hover, a topic switch or
 * a place pick redrew every one. As a memo of primitives, only the boxes whose own look changed are touched; the handlers must
 * be stable (the map passes callbacks that read the latest render through a ref).
 */
const MapBox = memo(function MapBox(p: Props) {
  return (
    <rect
      data-box=""
      data-state={p.dataState}
      data-active={p.active ? '' : undefined}
      x={p.x}
      y={p.y}
      width={p.size}
      height={p.size}
      rx={p.size * 0.14}
      fill={p.fill}
      opacity={p.opacity}
      style={{ cursor: p.pointer ? 'pointer' : 'default' }}
      onMouseEnter={p.hoverable ? () => p.onEnter(p.id, p.i) : undefined}
      onClick={() => p.onPick(p.id)}
    />
  )
})

export default MapBox
