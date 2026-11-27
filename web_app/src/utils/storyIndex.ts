// The `/stories` index (#1203): one card per data story, in the home Browse topics strip's order. Pure, so the order, the
// live / coming-soon split and the title rule are tested without rendering.
import type { TopicCaptionFacts, TopicSummary } from '../api/topics'
import { STORIES, type StoryScope } from './dataStory'
import { GUIDE_DECOR, buildTiles } from './homeTopicTiles'
import { CAPTION_COPY, captionText, pickCaption } from './storyCaption'

export interface StoryIndexCard {
  key: string
  /** The topic's name ("Short-term rentals"). */
  title: string
  /** The strip's one-line description, shown when there is no caption yet (and on coming-soon cards). */
  blurb: string
  status: 'live' | 'soon'
  /** The story it opens (`/stories/<story>`), when live. */
  story?: string
  /** The caption key (`CAPTION_COPY`) its title is picked with. */
  captionKey: string
}

const GUIDE_KEYS = new Set(GUIDE_DECOR.map((d) => d.key))

/**
 * Every data story, in the home strip's order (`buildTiles`): Data centers first, then the curated topics, then any other
 * live curated topic. Guides (starting a nonprofit, insurance) are not meeting stories, so they are left out. A tile the
 * strip calls "coming soon" stays coming soon here, with no story to link to.
 */
export function storyIndexCards(topics: TopicSummary[] | null | undefined): StoryIndexCard[] {
  return buildTiles(topics)
    .filter((t) => !GUIDE_KEYS.has(t.key))
    .map((t) => ({
      key: t.key,
      title: t.title,
      blurb: t.blurb,
      status: t.status === 'live' && t.story ? 'live' : 'soon',
      story: t.status === 'live' ? t.story : undefined,
      captionKey: t.captionKey,
    }))
}

/** The caption-facts slug a card reads (the same one the home strip reads for its tile). */
export function storyFactsSlug(card: Pick<StoryIndexCard, 'captionKey'>): string | null {
  const copy = CAPTION_COPY[card.captionKey]
  return (copy ? copy.facts : card.captionKey) || null
}

/** True when `facts` answer exactly the scope asked for, so a stale scope's numbers never show under the new label. */
function factsForScope(facts: TopicCaptionFacts | null | undefined, scope: StoryScope): facts is TopicCaptionFacts {
  if (!facts?.scope) return false
  const want = scope.stateCode ?? null
  if ((facts.scope.state_code ?? null) !== want) return false
  return (facts.scope.city ?? '').toLowerCase() === (want ? (scope.city ?? '').toLowerCase() : '')
}

/**
 * A card's title for the scope: the shared caption picker's title, the same one the home card and the story show. With no
 * facts the picker asks the topic's question; a registry story (data centers) asks its own question, as on the home card.
 */
export function storyCardTitle(card: StoryIndexCard, facts: TopicCaptionFacts | null | undefined, scope: StoryScope): string {
  const caption = pickCaption(card.captionKey, factsForScope(facts, scope) ? facts : null, scope)
  const registry = card.story ? STORIES[card.story] : undefined
  if (caption.kind === 'question' && registry) return registry.question
  return captionText(caption, CAPTION_COPY[card.captionKey]?.topic ?? card.title.toLowerCase())
}

/** The meetings on record for the scope, from the caption facts; null when not on record (never shown as zero). */
export function storyCardMeetings(facts: TopicCaptionFacts | null | undefined, scope: StoryScope): number | null {
  if (!factsForScope(facts, scope)) return null
  return typeof facts.meetings === 'number' && facts.meetings > 0 ? facts.meetings : null
}
