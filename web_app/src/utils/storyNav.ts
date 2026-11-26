import { STORIES } from './dataStory'
import { cap } from './stanceGame'

// Story-to-story navigation (#1102): the top progress bar, the numbered dots, the phone bar and the "Next story" card at the
// end of a story all read these pure helpers.

/** A story a reader can open today. */
export interface LiveStory {
  /** The path segment under `/stories/`. */
  id: string
  /** Its name in a sentence ("Short-term rentals"). */
  title: string
}

/**
 * The live stories, in the home page's order (#1025): the stories registry (`STORIES`, told by `DataStory`) first, then the
 * topic stories told by `TopicStory` (`/stories/short-term-rentals`). The topics still "coming soon" on the home strip are
 * not here, so the card never links to a story that doesn't exist.
 */
export const LIVE_STORIES: LiveStory[] = [
  ...Object.entries(STORIES).map(([id, s]) => ({ id, title: cap(s.topic) })),
  { id: 'short-term-rentals', title: 'Short-term rentals' },
]

/** The live story after `currentId`, or null at the end of the list (no wrap) or for a story not in it. */
export function nextLiveStory(currentId: string, stories: LiveStory[] = LIVE_STORIES): LiveStory | null {
  const i = stories.findIndex((s) => s.id === currentId)
  if (i < 0 || i >= stories.length - 1) return null
  return stories[i + 1]!
}

/** Where the end of a story leads: the next live story, or every data story when there is none. The scope query is kept. */
export function nextStoryLink(currentId: string, query: string, stories: LiveStory[] = LIVE_STORIES): { href: string; label: string; next: LiveStory | null } {
  const next = nextLiveStory(currentId, stories)
  if (next) return { href: `/stories/${encodeURIComponent(next.id)}${query}`, label: `Next story: ${next.title}`, next }
  return { href: `/stories${query}`, label: 'All data stories', next: null }
}

/** The share of the story reached, 0 to 1: the screen in view counts as reached ("1 of 8" is 1/8, the last screen is 1). */
export function storyProgress(active: number, count: number): number {
  if (count <= 0) return 0
  return Math.min(1, Math.max(0, (Math.min(Math.max(active, 0), count - 1) + 1) / count))
}

export type DotState = 'past' | 'now' | 'ahead'

/** Which dot is the screen in view; an index out of range is held to the nearest screen. */
export function currentDot(active: number, count: number): number {
  if (count <= 0) return -1
  return Math.min(Math.max(active, 0), count - 1)
}

/** One dot's state against the screen in view. */
export function dotState(i: number, active: number, count: number): DotState {
  const now = currentDot(active, count)
  return i === now ? 'now' : i < now ? 'past' : 'ahead'
}

/** True on the story's last screen, where the phone bar's Next goes on to the next story. */
export function isLastScreen(active: number, count: number): boolean {
  return count > 0 && currentDot(active, count) === count - 1
}
