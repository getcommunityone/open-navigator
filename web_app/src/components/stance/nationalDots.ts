/** The Overview's national dot grid and its colours (#970), shared by StoryDotMap and the drill-down transition (MapDrill, #1195). */
import { NATIONAL_BBOX, dotsFor, meetingColor, toFeats } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { HOUSE_THEME } from '../../utils/houseTheme'
import type { StateCount } from './StoryDotMap'

// The theme's light-to-brand teal steps; its last, near-black step is left out so the busiest states read as teal, not ink.
export const RAMP = HOUSE_THEME.ramp.slice(1, 5)
/** The map's margin around the national viewBox. */
export const NATIONAL_PAD = 4

/** The national grid of dots; each knows its state FIPS. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function nationalGrid(topo: any) {
  const feats = toFeats(topo, 'states').filter((f) => f.id !== '72')
  return { feats, ...dotsFor(feats, NATIONAL_BBOX, 90) }
}

/** A national dot's colour and radius factor from its state's real meeting count: the empty colour and a smaller dot for none. */
export function nationalPaint(byState: StateCount[] | null | undefined): (fips: string) => { color: string; rScale: number } {
  const counts = new Map((byState ?? []).map((s) => [s.state_code, s.meetings]))
  const max = Math.max(0, ...(byState ?? []).map((s) => s.meetings))
  return (fips) => {
    const code = STATE_FIPS_TO_CODE[fips]
    const n = code ? counts.get(code) : undefined
    return { color: meetingColor(n, max, RAMP, HOUSE_THEME.neutral), rScale: n ? 1 : 0.55 }
  }
}
