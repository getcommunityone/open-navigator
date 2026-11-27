import type { Stance } from './boxSplit'

export interface BoxPosition {
  side: Stance | null
  /** 0-based index among all boxes of this state (left to right, then top to bottom). */
  rank: number
  /** Total boxes belonging to this state. */
  stateCount: number
  /** 0-based index among boxes of the same stance band inside this state. */
  bandRank: number
  /** Total boxes in this box's stance band inside this state. */
  bandCount: number
}

/**
 * Maps a box's position (`rank` of `total`) into `count` contiguous zones (`0..count-1`).
 *
 * Contiguous zones mean moving slightly within one meeting's area keeps its recording playing without jitter, while
 * moving across the state or across stance bands switches cleanly through every available meeting/speaker passage.
 */
export function pickZoneIndex(rank: number, total: number, count: number): number {
  if (count <= 1 || total <= 1 || rank <= 0) return 0
  const clamped = Math.min(total - 1, Math.max(0, Math.floor(rank)))
  return Math.min(count - 1, Math.floor((clamped * count) / total))
}

/**
 * Maps an API topic `public_stance` value (`against` | `for` | `split` | `silent` | null) to a map box band side.
 * `split` maps to `neutral` (the plum band on topic maps); `silent` and unknown values carry no side.
 */
export function stanceFromPublicLean(publicStance: string | null | undefined): Stance | null {
  if (publicStance === 'against') return 'against'
  if (publicStance === 'for') return 'for'
  if (publicStance === 'split') return 'neutral'
  return null
}

/**
 * Picks the passage to show when hovering one box on `StoryStatesMap` (#1357):
 * - Named speakers rank first within any pool so box 0 / keyboard focus leads with a named speaker, while keeping
 *   unnamed meeting passages reachable across the state's other boxes.
 * - When the hovered box sits in a stance band (`against`, `for`, `question`, `neutral`), quotes for that side are
 *   preferred (`neutral` includes `question` speakers — drawn in the plum band per #1110 — and untagged meeting
 *   passages rather than repeating an opposing/supporting speaker).
 * - Within the matched pool, `pickZoneIndex` assigns contiguous zones so hovering different parts of the state walks
 *   through every passage without flickering on every adjacent box.
 */
export function pickBoxQuote<T extends { side?: Stance | null; band?: Stance | null; speakerName?: string | null }>(
  box: BoxPosition,
  quotes: readonly T[],
): T | undefined {
  if (quotes.length === 0) return undefined
  const ordered = [...quotes.filter((q) => Boolean(q.speakerName)), ...quotes.filter((q) => !q.speakerName)]
  const bandOf = (q: T): Stance | null => q.band ?? q.side ?? null

  if (box.side) {
    const bandPool =
      box.side === 'neutral'
        ? ordered.filter((q) => {
            const s = bandOf(q)
            return s === 'neutral' || s === 'question' || s == null
          })
        : ordered.filter((q) => bandOf(q) === box.side)
    if (bandPool.length > 0) {
      return bandPool[pickZoneIndex(box.bandRank, box.bandCount, bandPool.length)]
    }
  }

  return ordered[pickZoneIndex(box.rank, box.stateCount, ordered.length)]
}
