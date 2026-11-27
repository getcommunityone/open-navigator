export interface HoverBadgeLayout {
  x: number
  y: number
  width: number
  height: number
  rx: number
  textX: number
  textY: number
  fontSize: number
  placed: 'above' | 'below'
}

/**
 * Computes an SVG pill badge position anchored to a hovered state's bounding box (#1360).
 * Places the badge just above the state by default, flips below when near the top of the viewBox, and clamps
 * horizontally/vertically inside the viewBox so border states (WA, ME, FL, AK, HI) never clip.
 */
export function layoutHoverBadge(
  featBbox: readonly [number, number, number, number],
  viewBox: readonly [number, number, number, number],
  label: string,
  step: number,
): HoverBadgeLayout {
  const [fx0, fy0, fx1, fy1] = featBbox
  const [vx, vy, vw, vh] = viewBox
  const margin = Math.max(4, step * 0.5)
  const gap = Math.max(5, step * 0.55)
  const fontSize = Math.max(12, Math.min(18, step * 1.18))
  const height = fontSize * 1.95
  const rawWidth = Math.max(fontSize * 6, label.length * fontSize * 0.56 + fontSize * 1.8)
  const width = Math.min(vw - margin * 2, rawWidth)

  const cx = (fx0 + fx1) / 2
  const minX = vx + margin
  const maxX = Math.max(minX, vx + vw - width - margin)
  const x = Math.min(maxX, Math.max(minX, cx - width / 2))

  const aboveY = fy0 - height - gap
  const belowY = fy1 + gap
  const minY = vy + margin
  const maxY = Math.max(minY, vy + vh - height - margin)
  const placed: 'above' | 'below' = aboveY >= minY ? 'above' : 'below'
  const y = Math.min(maxY, Math.max(minY, placed === 'above' ? aboveY : belowY))

  return {
    x,
    y,
    width,
    height,
    rx: height / 2,
    textX: x + width / 2,
    textY: y + height / 2,
    fontSize,
    placed,
  }
}
