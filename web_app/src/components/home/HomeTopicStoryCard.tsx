import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicCaptionFacts, fetchTopicStanceMap, fetchTopicStates } from '../../api/topics'
import { topicStanceForMap } from '../../utils/topicStance'
import { quoteStanceNote, topicPositions } from '../../utils/topicPositions'
import { storyScopeLabel, type StoryScope } from '../../utils/dataStory'
import { useStoryScope } from '../../hooks/useStoryScope'
import { CAPTION_COPY, captionSubhead, captionText, isLongTitle, pickCaption, storyStartLabel } from '../../utils/storyCaption'
import '../../styles/story-actions.css'
import type { TopicStoryDef } from '../../utils/topicStories'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'
import HomeStoryTitle, { HomeStorySubhead } from './HomeStoryTitle'
import { storyStartHref } from '../../utils/storyNav'

/** A state's map passages, newest first, at most this many. */
const QUOTES_PER_STATE = 12

interface Props {
  def: TopicStoryDef
  /** The place asked (the URL's); the card speaks for the level `useStoryScope` resolves (#1285). */
  scope: StoryScope
  /** "?state=AL&city=…" (or empty): carried by every link. */
  query: string
  /** A place picked in the title's place control (#1206); see `HomeDataStories`. */
  onPlaceApply?: (stateCode: string | null, city: string | null) => void
}

/**
 * The home card for one topic story (#1013, #1133): its caption for the page's scope (#1125), its lede, Start the story,
 * and the map of meetings per state with each state's newest verbatim passage. Every figure is a real count.
 */
export default function HomeTopicStoryCard({ def, scope: asked, query, onPlaceApply }: Props) {
  const topicNoun = CAPTION_COPY[def.slug]?.topic ?? def.subject.toLowerCase()
  // The place the story speaks for (#1285): too few meetings for the city (or state) steps up a level, and says why.
  const placeScope = useStoryScope(def.slug, topicNoun, asked.stateCode, asked.city)
  const scope: StoryScope = placeScope.effective
  const label = storyScopeLabel(scope)
  // The map's hover card goes in the text column, under Start (#1277), never over the map.
  const [cardSlot, setCardSlot] = useState<HTMLDivElement | null>(null)
  const states = useQuery({
    queryKey: ['topic-story', def.topicId, 'states'],
    queryFn: () => fetchTopicStates(def.topicId),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const facts = useQuery({
    queryKey: ['caption-facts', def.slug, scope.stateCode ?? '', scope.city ?? ''],
    queryFn: () => fetchTopicCaptionFacts(def.slug, scope.stateCode, scope.city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  // The AI reading of each state's meetings (#1127, #1182), the same four-colour split as the topic story's map, so the
  // title's lean claim and the map beside it say the same thing. No reading yet, or a failed request, leaves the plain
  // meetings map.
  const stanceQ = useQuery({
    queryKey: ['topic-story', def.topicId, 'state-map'],
    queryFn: () => fetchTopicStanceMap(def.topicId),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const stance = useMemo(() => topicStanceForMap(stanceQ.data), [stanceQ.data])
  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    for (const m of states.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      const q: StateQuote = {
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        // Where the public stood at the quoted meeting (#1230): the API picks a meeting where it took a side first.
        stanceNote: quoteStanceNote(def.slug, CAPTION_COPY[def.slug]?.topic ?? def.subject.toLowerCase(), m.public_stance),
        url: m.video_url ?? null,
        videoId: m.video_id ?? null,
        // Named only where the speaker introduced themselves on the record (#1231).
        speakerName: m.speaker_display_name ?? null,
        role: m.speaker_display_name ? (m.speaker_role ?? null) : null,
      }
      const list = out.get(m.state_code)
      if (!list) out.set(m.state_code, [q])
      else if (list.length < QUOTES_PER_STATE) list.push(q)
    }
    // At city level (#1285) the state shows only that city's passages: label and quotes move together.
    if (scope.city && scope.stateCode) {
      const c = scope.city.toLowerCase()
      out.set(scope.stateCode, (out.get(scope.stateCode) ?? []).filter((x) => x.place.toLowerCase().startsWith(c)))
    }
    return out
  }, [states.data, def.slug, def.subject, scope.city, scope.stateCode])
  const caption = pickCaption(def.slug, facts.data, scope)
  const title = captionText(caption, topicNoun)
  // Start opens the story past its cover (#1222).
  const href = storyStartHref(def.slug, query)

  return (
    <div className="home-story-card">
      <div className="home-story-text">
        <p className="font-mono-x home-story-eyebrow">Data story · {def.title}</p>
        <h1
          id="home-story-dc"
          className={`font-display home-story-headline${isLongTitle(title) ? ' is-long' : ''}`}
          aria-busy={facts.isPending || undefined}
          style={facts.isPending ? { visibility: 'hidden' } : undefined}
        >
          <HomeStoryTitle caption={caption} topic={topicNoun} scope={scope} onPlaceApply={onPlaceApply} />
        </h1>
        {/* A broader scope's title (#1222): the line under it names the place in scope (as its control); else the lede. */}
        <HomeStorySubhead
          caption={caption}
          topic={topicNoun}
          scope={scope}
          onPlaceApply={onPlaceApply}
          subhead={
            placeScope.resolved.reason ??
            (caption.kind === 'wider_position' || caption.kind === 'wider_sentiment' ? captionSubhead(caption, def.slug, scope) : def.lede)
          }
        />
        <p className="home-story-basis">
          {caption.basis ?? 'Counted from local meeting recordings and transcripts that mention the topic.'}
        </p>
        <div className="home-story-actions">
          <Link to={href} className="home-story-start">
            {storyStartLabel(def.slug, label, def.subject)} <span aria-hidden="true">→</span>
          </Link>
        </div>
        <HomeStoryDrill slotRef={setCardSlot} />
      </div>
      <div className="home-story-map">
        {states.isError ? (
          <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
        ) : (
          <StoryStatesMap
            byState={states.data?.states}
            quotes={quotes}
            highlight={scope.stateCode ?? null}
            zoom={
              scope.stateCode
                ? {
                    stateCode: scope.stateCode,
                    pin: placeScope.pin,
                    note: asked.city && placeScope.pinKnown && !placeScope.pin ? `No map location on record for ${asked.city}.` : null,
                  }
                : null
            }
            href={(code) => `/stories/${encodeURIComponent(def.slug)}?state=${encodeURIComponent(code)}`}
            subject={topicNoun.toLowerCase()}
            stance={stance && stance.length > 0 ? stance : undefined}
            stanceUnit="meetings"
            positions={topicPositions(def.slug)}
            cardSlot={cardSlot}
          />
        )}
      </div>
    </div>
  )
}

/**
 * The drill-down line under the hero's buttons (#1176): says how to go deeper, so the reader knows the map is the way in.
 * The scope in effect is named by the title's place control (#1206; CLAUDE.md, scope label rule), so this line no longer
 * repeats it. It is also the slot the map's desktop hover card fills (#1277): the card replaces the line while a state is
 * hovered, and the slot keeps its height so the page doesn't jump.
 */
export function HomeStoryDrill({ slotRef, hint = 'Pick a state on the map to open its story.' }: { slotRef?: (el: HTMLDivElement | null) => void; hint?: string }) {
  return (
    <div className="map-card-slot" ref={slotRef}>
      <p className="home-story-drill map-card-slot-hint">{hint}</p>
    </div>
  )
}
