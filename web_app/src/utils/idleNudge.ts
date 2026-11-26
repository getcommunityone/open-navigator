// When to draw attention to the next step (#930). A reader who has stopped (no scroll, tap or key for a while) on a screen
// that has a next step gets a small cue on the primary action: a few times, spaced out, then it rests. Pure timing only; the
// hook `useIdleNudge` supplies the clock and the page state.

/** How long the reader must be still before the first cue. */
export const NUDGE_IDLE_MS = 6000
/** The gap between one cue and the next. */
export const NUDGE_REPEAT_MS = 8000
/** Cues per screen before it rests. Any interaction starts the count again. */
export const NUDGE_MAX = 3
/** How long one cue lasts on screen (the CSS animations run inside it). */
export const NUDGE_CYCLE_MS = 1400
/** A screen's own entrance (blocks rising in, the chart's dots drawing): the idle clock starts after it. */
export const NUDGE_ENTRANCE_MS = 1200
/** How often the hook looks at the clock. */
export const NUDGE_TICK_MS = 250

export interface NudgeBlocks {
  /** A dialog is open (the place picker). */
  dialog?: boolean
  /** A data table is open: the reader is reading it. */
  table?: boolean
  /** A text input, select or editable field has focus. */
  typing?: boolean
  /** The reader is selecting text. */
  selecting?: boolean
  /** The tab is hidden. */
  hidden?: boolean
  /** The screen has no next step (the last screen, or nothing to press). */
  noNext?: boolean
}

export interface NudgeState {
  /** Now, in milliseconds on any steady clock. */
  now: number
  /** When the reader last scrolled, tapped or typed; or when the screen's entrance finished, if that is later. */
  lastInteraction: number
  /** When the last cue began, or null when none has been shown since the last interaction. */
  lastNudge: number | null
  /** Cues shown since the last interaction. */
  shown: number
  blocked?: NudgeBlocks
}

export const isBlocked = (b: NudgeBlocks | undefined): boolean =>
  Boolean(b && (b.dialog || b.table || b.typing || b.selecting || b.hidden || b.noNext))

/** Whether to show a cue now. */
export function shouldNudge(s: NudgeState): boolean {
  if (isBlocked(s.blocked)) return false
  if (s.shown >= NUDGE_MAX) return false
  if (s.now - s.lastInteraction < NUDGE_IDLE_MS) return false
  if (s.lastNudge != null && s.now - s.lastNudge < NUDGE_REPEAT_MS) return false
  return true
}

/** The idle clock's starting point for a screen that has just arrived: its entrance plays first. */
export function arrivalTime(now: number, entranceMs: number = NUDGE_ENTRANCE_MS): number {
  return now + Math.max(0, entranceMs)
}
