// Which topics have a live story (#1133). Every curated topic with at least one linked meeting gets a story told by
// `TopicStory` at `/stories/<query_id>`, derived at runtime from `GET /api/topics`, so a topic added later goes live with no
// code change. Stories in the `STORIES` registry (data centers) stay on `DataStory`.
import type { TopicSummary } from '../api/topics'
import { STORIES } from './dataStory'
import type { LiveStory } from './storyNav'

export interface TopicStoryDef {
  slug: string
  topicId: number
  title: string
  /** "Short-term rentals came up in …": the noun phrase for the topic. */
  subject: string
  lede: string
  /** The API listing the platform companies this story names (#1015), when it has one. */
  companiesPath?: string
  /** National meetings linked to the topic (from the topics API). */
  meetings: number
}

/** Hand-written copy for topics that have it; any other curated topic gets a plain lede from its name. */
const TOPIC_COPY: Record<string, Partial<Pick<TopicStoryDef, 'title' | 'subject' | 'lede' | 'companiesPath'>>> = {
  'short-term-rentals': {
    lede: 'Airbnb, VRBO and vacation rentals: where local governments are talking about them, in the words said at the meeting.',
    companiesPath: '/short-term-rentals/companies',
  },
  'license-plate-readers': {
    lede: 'Flock Safety cameras and other automated plate readers: who uses them, for what, and the contracts behind them, in the words said at the meeting.',
  },
  // Shown as "Gun control" (#1237), the question the AI reading asks; the curated_topics seed and /api/topics keep "Guns".
  guns: {
    title: 'Gun control',
    subject: 'Gun control',
    lede: 'Firearm rules, gun shows and ranges, and gunshot detection, as councils weigh them, in the words said at the meeting.',
  },
  pickleball: { lede: 'Courts, noise and new venues, as councils and parks boards weigh them, in the words said at the meeting.' },
}

/** True for a curated topic with linked meetings: it can be told as a story. */
export function isLiveTopic(t: Pick<TopicSummary, 'source' | 'meeting_count' | 'query_id'>): boolean {
  return t.source === 'curated' && Boolean(t.query_id) && (t.meeting_count ?? 0) > 0
}

/** The topic stories, keyed by slug: curated topics with meetings, minus the registry's own stories (data centers). */
export function deriveTopicStories(topics: TopicSummary[] | null | undefined): Record<string, TopicStoryDef> {
  const out: Record<string, TopicStoryDef> = {}
  for (const t of topics ?? []) {
    if (!isLiveTopic(t) || STORIES[t.query_id!]) continue
    const slug = t.query_id!
    const copy = TOPIC_COPY[slug] ?? {}
    out[slug] = {
      slug,
      topicId: t.topic_id,
      title: copy.title ?? t.name,
      subject: copy.subject ?? t.name,
      lede: copy.lede ?? `What local governments said about ${t.name.toLowerCase()}, in the words said at the meeting.`,
      companiesPath: copy.companiesPath,
      meetings: t.meeting_count ?? 0,
    }
  }
  return out
}

/** Which page tells `/stories/:storyId`: the registry's `DataStory`, otherwise the topic's `TopicStory`. */
export function storyRoute(storyId: string): 'data' | 'topic' {
  return STORIES[storyId] ? 'data' : 'topic'
}

/** The live stories in order: the registry first, then topic stories by national meetings (most first). */
export function liveStories(topicStories: Record<string, TopicStoryDef>): LiveStory[] {
  const topics = Object.values(topicStories).sort((a, b) => b.meetings - a.meetings || a.title.localeCompare(b.title))
  return [
    ...Object.entries(STORIES).map(([id, s]) => ({ id, title: s.topic.charAt(0).toUpperCase() + s.topic.slice(1) })),
    ...topics.map((t) => ({ id: t.slug, title: t.title })),
  ]
}
