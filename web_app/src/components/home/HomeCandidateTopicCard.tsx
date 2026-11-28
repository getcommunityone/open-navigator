import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicStates } from '../../api/topics'
import type { YoyResponse, YoyTopic } from '../../api/topicsYoy'
import { stanceFromPublicLean } from '../../utils/mapQuote'
import { changeLabel, relChange, topicDestination, yearBLabel } from '../../utils/topicsYoy'
import TopicCountyMap from '../stance/TopicCountyMap'
import PlaceControl from '../stance/PlaceControl'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'
import { HomeStoryDrill } from './HomeTopicStoryCard'
import { TopicSelect, type TopicControl } from './HomeStoryTitle'
import '../../styles/story-actions.css'
import '../../styles/home-place.css'

const QUOTES_PER_STATE = 12
const fmt = (n: number) => n.toLocaleString('en-US')
const pct = (x: number) => `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`

interface Props {
  topic: YoyTopic
  /** The `/api/topics/yoy` response the topic came from: its scope is the place every number here speaks for. */
  yoy: YoyResponse
  onPlaceApply?: (stateCode: string | null, city: string | null) => void
  topicControl?: TopicControl
}

/**
 * The home hero for a topic with no data story yet (#1416): a rising or heated topic from the pills. Its headline is
 * built from the real yoy counts for the place, the map is the topic's own meetings (county map at state scope, state
 * map nationally), and the one action opens its meetings in Browse topics, so the pill is never a dead end. Where
 * nothing was recorded, it says so.
 */
export default function HomeCandidateTopicCard({ topic, yoy, onPlaceApply, topicControl }: Props) {
  const navigate = useNavigate()
  const [cardSlot, setCardSlot] = useState<HTMLDivElement | null>(null)
  const scope = yoy.scope
  const stateCode = scope.state_code ?? undefined
  const city = scope.city
  const place = city ? `${city}, ${stateCode}` : (scope.state ?? 'America')
  const subject = topic.name.toLowerCase()
  const [openPlace, setOpenPlace] = useState(false)
  const states = useQuery({
    queryKey: ['topic-story', topic.topic_id, 'states', 3],
    queryFn: () => fetchTopicStates(topic.topic_id, { quotes_per_state: 3 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    for (const m of states.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      const q: StateQuote = {
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        band: stanceFromPublicLean(m.public_stance),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        url: m.video_url ?? null,
        videoId: m.video_id ?? null,
        speakerName: m.speaker_display_name ?? null,
        role: m.speaker_display_name ? (m.speaker_role ?? null) : null,
      }
      const list = out.get(m.state_code)
      if (!list) out.set(m.state_code, [q])
      else if (list.length < QUOTES_PER_STATE) list.push(q)
    }
    if (city && stateCode) {
      const c = city.toLowerCase()
      out.set(stateCode, (out.get(stateCode) ?? []).filter((x) => x.place.toLowerCase().startsWith(c)))
    }
    return out
  }, [states.data, city, stateCode])

  const yearLabel = yearBLabel(yoy)
  const none = topic.meetings_a === 0 && topic.meetings_b === 0
  const change = topic.comparable && topic.share_a != null && topic.share_b != null ? relChange(topic.share_a, topic.share_b) : null
  const subhead = none
    ? `Nothing in the ${fmt(yoy.recorded_a + yoy.recorded_b)} meetings recorded here in ${yoy.year_a} and ${yoy.year_b} discussed it.`
    : change != null && topic.share_a != null && topic.share_b != null
      ? `That is ${pct(topic.share_b)} of the meetings recorded here, ${topic.share_b >= topic.share_a ? 'up' : 'down'} from ${pct(topic.share_a)} in ${yoy.year_a} (${changeLabel(change)}).`
      : `${fmt(topic.meetings_a)} in ${yoy.year_a}. Too few meetings to compare the two years.`
  const heat =
    typeof topic.heat_mean === 'number' && (topic.heat_rated ?? 0) > 0
      ? ` Speakers' heat on it averages ${topic.heat_mean.toFixed(1)} of 5 (${fmt(topic.heat_rated ?? 0)} speakers rated).`
      : ''
  const href = topicDestination(topic, stateCode, city)
  const where = (code: string) => `/browse-topics?${new URLSearchParams({ topic_id: String(topic.topic_id), state: code }).toString()}`
  const drill = (c: string | null) => {
    if (!stateCode) return
    const p = new URLSearchParams({ topic_id: String(topic.topic_id), state: stateCode })
    if (c) p.set('city', c)
    navigate(`/browse-topics?${p.toString()}`)
  }
  const statesMap = (
    <StoryStatesMap
      byState={states.data?.states}
      quotes={quotes}
      highlight={stateCode ?? null}
      zoom={stateCode ? { stateCode, pin: null, note: null } : null}
      href={where}
      subject={subject}
      stanceUnit="meetings"
      cardSlot={cardSlot}
    />
  )
  const topicWord = topicControl ? <TopicSelect word={topic.name} control={topicControl} /> : topic.name
  const placeBlank = onPlaceApply ? (
    <span className="home-place-nowrap">
      <PlaceControl variant="blank" themeClassName="home-place" display={place} stateCode={stateCode} city={city} open={openPlace} onOpenChange={setOpenPlace} onApply={onPlaceApply} />
    </span>
  ) : (
    place
  )

  return (
    <div className="home-story-card" data-hero-topic={topic.slug} data-hero-kind="meetings">
      <div className="home-story-text">
        <p className="font-mono-x home-story-eyebrow">Meetings · {topic.name}</p>
        <h1 id="home-story-dc" className="font-display home-story-headline">
          {none ? (
            <>No recorded meeting in {placeBlank} has discussed {topicWord} in {yearLabel}.</>
          ) : (
            <>
              {topicWord} came up in {fmt(topic.meetings_b)} {topic.meetings_b === 1 ? 'meeting' : 'meetings'} in {placeBlank}, {yearLabel}.
            </>
          )}
        </h1>
        <p className="home-story-subhead">{subhead}</p>
        <p className="home-story-basis">
          Counted from local meeting recordings and transcripts that mention the topic.{heat}
        </p>
        <div className="home-story-actions">
          <Link to={href} className="home-story-start">
            See {subject} meetings <span aria-hidden="true">→</span>
          </Link>
        </div>
        <HomeStoryDrill slotRef={setCardSlot} hint={stateCode ? 'Pick a county or a town on the map to open its meetings.' : 'Pick a state on the map to open its meetings.'} />
      </div>
      <div className="home-story-map">
        {states.isError ? (
          <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
        ) : stateCode ? (
          <TopicCountyMap
            topicId={topic.topic_id}
            stateCode={stateCode}
            scopeCity={city}
            scopeLabel={place}
            subject={subject}
            cardSlot={cardSlot}
            onPickState={(code) => onPlaceApply?.(code, null)}
            onDrill={drill}
            chrome={false}
            fallback={statesMap}
          />
        ) : (
          statesMap
        )}
      </div>
    </div>
  )
}

