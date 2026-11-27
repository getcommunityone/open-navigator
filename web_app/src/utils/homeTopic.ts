// Which story the home hero shows (#1350): carried by ?topic=<slug> (the legacy ?story= still reads), data centers by default.
export const DEFAULT_STORY = 'data-centers'

/** The story asked for in the URL: `topic` wins over the legacy `story`; '' when neither is present. */
export function askedStory(sp: URLSearchParams): string {
  return sp.get('topic') ?? sp.get('story') ?? ''
}

/** The params with the story set: the default story carries no param, and the legacy `story` is dropped. */
export function withStory(prev: URLSearchParams, slug: string): URLSearchParams {
  const n = new URLSearchParams(prev)
  n.delete('story')
  if (slug === DEFAULT_STORY) n.delete('topic')
  else n.set('topic', slug)
  return n
}

/** The next tab index for a key in a horizontal tablist of `n` tabs, or null when the key is not one of ours. */
export function tabKeyTarget(key: string, current: number, n: number): number | null {
  if (n <= 0) return null
  if (key === 'ArrowRight') return (current + 1) % n
  if (key === 'ArrowLeft') return (current - 1 + n) % n
  if (key === 'Home') return 0
  if (key === 'End') return n - 1
  return null
}
