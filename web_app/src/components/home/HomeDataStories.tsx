import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { CAPTION_COPY, captionSubhead, captionText, isLongTitle, pickCaption, storyStartLabel } from '../../utils/storyCaption'
import '../../styles/story-actions.css'
import HomeTopicBar from './HomeTopicBar'
import { askedStory as askedStoryOf, withStory } from '../../utils/homeTopic'
import { storyTopicOptions } from '../../utils/storyNav'
import HomeTopicStoryCard, { HomeStoryDrill } from './HomeTopicStoryCard'
import HomeCandidateTopicCard from './HomeCandidateTopicCard'
import { useHotTopics } from '../../hooks/useHotTopics'
import type { HotPill } from '../../utils/hotTopics'
import { prefetchHeroTopic } from '../../utils/heroPrefetch'
import { captureDomBoxes, captureDomBoxesChunked, type ParticleBox } from '../../utils/boxFlight'
import HomeStoryTitle, { HomeStorySubhead } from './HomeStoryTitle'
import { useTopicStories } from '../../hooks/useTopicStories'
import { useStoryScope } from '../../hooks/useStoryScope'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { useBoxFlight } from '../stance/BoxFlightProvider'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'
import HomeOutcomesScroller from './HomeOutcomesScroller'
import { storyStartHref } from '../../utils/storyNav'
import { scopedMeetingHref } from '../stance/quoteCardUtils'
import { dataCenterQuoteNote } from '../../utils/topicPositions'
import StoryCountyMap from '../stance/StoryCountyMap'
import MapSkeleton, { useStateAspect } from '../stance/MapSkeleton'
import CoverageLine from '../stance/CoverageLine'


interface Props {
  /** The home page's place, so the Start button and the topic links carry it (CLAUDE.md, scope label rule). */
  stateCode?: string
  city?: string | null
  /**
   * A place picked in the title's place control (#1206): a state (and city), or null/null for the United States. The home
   * page applies it the way the header's place control does, so every label and the data move together.
   */
  onPlaceApply?: (stateCode: string | null, city: string | null) => void
}

const STORY = STORIES['data-centers']!
const MAP_SEL = '.home-story-map'

/** Hide the hero map's boxes at once (still measurable), failsafe-cleared if no flight takes over; the provider clears it on finish. */
function prehideHeroMap() {
  const el = document.querySelector(MAP_SEL)
  if (!el) return
  el.setAttribute('data-box-flight-prehide', '1')
  window.setTimeout(() => el.removeAttribute('data-box-flight-prehide'), 3500)
}

/** A resting snapshot of the hero's boxes and the scroll it was taken at, so a later scroll only shifts it. */
interface HeroSnap {
  boxes: ParticleBox[]
  sx: number
  sy: number
  w: number
}
function snapToViewport(s: HeroSnap | null): ParticleBox[] {
  if (!s || s.w !== window.innerWidth) return []
  const dx = window.scrollX - s.sx
  const dy = window.scrollY - s.sy
  return s.boxes.map((b) => ({ ...b, x: b.x - dx, y: b.y - dy })).filter((b) => b.y + b.h / 2 > 0 && b.y - b.h / 2 < window.innerHeight)
}
/** A state's map passages, in order (speakers' own words first, then the API's map-quote meetings, #1230), at most this many. */
const QUOTES_PER_STATE = 12

function pushQuote(out: Map<string, StateQuote[]>, code: string, q: StateQuote) {
  const list = out.get(code)
  if (!list) out.set(code, [q])
  else if (list.length < QUOTES_PER_STATE) list.push(q)
}

/**
 * Home `#data-stories`, the top of the home page (#975, #985, #989, #995):
 * - the story's title from the caption picker (#1125), the same one the story header and Overview use, for the page's
 *   scope, with its scoped subhead (#1134), basis line, Start and Next story (the numbered points were removed at the
 *   owner's request, #1182: they took too much of the first screen);
 * - a US map of small boxes in each state's shape (#1087), split by the real counts of speakers for, against, asking a
 *   question or taking no side where any are on record, each state linking to its story, and a card quoting one of the
 *   state's real passages, verbatim, with where and when it was said;
 * - the compact topic chip bar above the hero (#1350, #1371): picks the story the card shows; **Compare all** opens the YoY page.
 */
export default function HomeDataStories({ stateCode, city = null, onPlaceApply }: Props) {
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  // The place asked (the URL keeps it) and the place the story speaks for (#1285): a city with fewer than 5 meetings steps
  // up to its state, a state with fewer to the country, and the subtitle says why. Title, counts, quotes and map follow it.
  const asked = { stateCode, stateName, city: stateCode ? city : null }
  const q = scopeQuery(asked)
  const placeScope = useStoryScope('data-centers', CAPTION_COPY['data-centers']!.topic, stateCode, asked.city)
  const scope = { ...placeScope.effective, stateCode: placeScope.effective.stateCode }
  const label = storyScopeLabel(scope)
  // The title (#1125): the caption picker over the caption facts for the scope used, shared with the story header.
  const dcFacts = useQuery({
    queryKey: ['caption-facts', 'data-centers', scope.stateCode ?? '', scope.city ?? ''],
    queryFn: () => fetchTopicCaptionFacts('data-centers', scope.stateCode, scope.city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const pending = dcFacts.isPending
  const dcCaption = pickCaption('data-centers', dcFacts.data, scope)
  const dcSubhead = placeScope.resolved.reason ?? captionSubhead(dcCaption, 'data-centers', scope)
  const dcTopic = CAPTION_COPY['data-centers']!.topic
  const dcTitle = captionText(dcCaption, dcTopic)
  // Which story the card shows (#1025): Data centers by default; Browse topics switches it, carried as ?story= so a
  // refresh, a deep link or Back keeps it (CLAUDE.md, scope via the URL).
  const [sp, setSp] = useSearchParams()
  // The map's hover card goes in the text column, under Start (#1277), never over the map.
  const [cardSlot, setCardSlot] = useState<HTMLDivElement | null>(null)
  const mapWrapRef = useRef<HTMLDivElement | null>(null)
  const reduced = usePrefersReducedMotion()
  const boxFlight = useBoxFlight()
  // Any live topic story can be shown (#1133); a rising or heated topic with no story gets the meeting view (#1416);
  // an unknown ?topic= shows data centers.
  const topicStories = useTopicStories()
  const hot = useHotTopics(topicStories.live, stateCode, asked.city)
  const askedStory = askedStoryOf(sp)
  const topicDef = askedStory ? topicStories.stories[askedStory] : undefined
  const candidate = !topicDef && askedStory && askedStory !== 'data-centers' ? hot.yoy?.topics.find((t) => t.slug === askedStory) : undefined
  // A deep-linked topic we cannot place yet: hold the hero (no data-centers flash) until the catalog and yoy have answered.
  const resolving = Boolean(askedStory && askedStory !== 'data-centers' && !topicDef && !candidate && (topicStories.pending || hot.pending))
  const story = topicDef || candidate ? askedStory : 'data-centers'
  // The row: the hot pills, plus the shown topic when it is not among them (a deep link), so it always reads as active.
  const pills = useMemo<HotPill[]>(() => {
    if (!candidate || hot.pills.some((p) => p.id === story)) return hot.pills
    const one: HotPill = { id: candidate.slug, title: candidate.name, topicId: candidate.topic_id, live: false, rise: null, heat: null, heatRated: 0, score: 0, meetings: candidate.meetings_b }
    return [one, ...hot.pills]
  }, [hot.pills, candidate, story])
  const [pendingId, setPendingId] = useState<string | null>(null)
  const switchSeq = useRef(0)
  const qc = useQueryClient()
  const hasStory = (id: string) => id === 'data-centers' || Boolean(topicStories.stories[id])
  const prefetch = (id: string) => {
    const m = pills.find((x) => x.id === id)
    if (!m) return Promise.resolve()
    return prefetchHeroTopic(qc, { id, topicId: m.topicId ?? topicStories.stories[id]?.topicId ?? null, story: hasStory(id) }, stateCode, asked.city)
  }
  // ?topic= (the legacy ?story= still reads) keeps the place and replaces history, so Back leaves the page (#1350).
  // The switch (#1416): the new topic's data is prefetched first, then the hero map's boxes fly into the new layout
  // (#1404's particle flight). A newer pick supersedes an older one; reduced motion swaps with a crossfade (CSS).
  const selectStory = (next: string) => {
    if (next === story && !pendingId) return
    const mine = ++switchSeq.current
    setPendingId(next)
    const boxes = reduced ? [] : snapToViewport(heroSnap.current)
    const wait = Promise.race([prefetch(next), new Promise((r) => window.setTimeout(r, 1500))])
    void wait.then(() => {
      if (mine !== switchSeq.current) return
      flushSync(() => {
        setSp((prev) => withStory(prev, next), { replace: true, preventScrollReset: true })
        setPendingId(null)
      })
      if (!reduced && boxes.length > 0) {
        // Hide the new map's boxes now, so the old ones carry the eye across and no frame shows both.
        prehideHeroMap()
        boxFlight.launch({ boxes, targetSelector: MAP_SEL })
      }
    })
  }
  // A place change flies too (#1416): national -> state or city, state -> national, state -> state, and the city -> state
  // fallbacks. The hero's resting boxes are remembered; the new place's data is prefetched where the pick starts here
  // (the title's place control, a state tapped on the county map); the header's own toggle has no hook, so there the
  // flight waits for the new map's boxes (the provider holds the old ones until they are drawn).
  const placeKey = `${stateCode ?? ''}|${stateCode ? (asked.city ?? '') : ''}`
  const heroSnap = useRef<HeroSnap | null>(null)
  const pendingFrom = useRef<ParticleBox[] | null>(null)
  const prevPlace = useRef(placeKey)
  const placeSeq = useRef(0)
  // The resting snapshot is read in slices off the main thread's critical path (thousands of boxes), after the map settles.
  const snapSeq = useRef(0)
  useEffect(() => {
    if (reduced) return
    const mine = ++snapSeq.current
    const snap = async () => {
      if (boxFlight.isFlying) return
      const sx = window.scrollX
      const sy = window.scrollY
      const boxes = await captureDomBoxesChunked(document.querySelector(MAP_SEL), { isStale: () => mine !== snapSeq.current || window.scrollY !== sy })
      if (boxes.length > 0 && mine === snapSeq.current) heroSnap.current = { boxes, sx, sy, w: window.innerWidth }
    }
    const t1 = window.setTimeout(() => void snap(), 900)
    const t2 = window.setTimeout(() => void snap(), 2200)
    // A phone shows the headline first and the map below it: re-read once a scroll or resize settles, so the map's boxes
    // are in the snapshot whenever they are on screen.
    let t3 = 0
    const again = () => {
      window.clearTimeout(t3)
      t3 = window.setTimeout(() => void snap(), 350)
    }
    window.addEventListener('scroll', again, { passive: true })
    window.addEventListener('resize', again)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      window.clearTimeout(t3)
      window.removeEventListener('scroll', again)
      window.removeEventListener('resize', again)
    }
  }, [placeKey, story, reduced, boxFlight])
  useLayoutEffect(() => {
    if (prevPlace.current === placeKey) return
    prevPlace.current = placeKey
    const map = document.querySelector(MAP_SEL)
    if (reduced) {
      // Reduced motion: the map crossfades in place.
      map?.removeAttribute('data-xfade')
      void (map as HTMLElement | null)?.offsetWidth
      map?.setAttribute('data-xfade', '1')
      return
    }
    const from = pendingFrom.current ?? snapToViewport(heroSnap.current)
    pendingFrom.current = null
    if (from.length === 0) return
    prehideHeroMap()
    boxFlight.launch({ boxes: from, targetSelector: MAP_SEL })
  }, [placeKey, reduced, boxFlight])
  const applyPlace = onPlaceApply
    ? (code: string | null, c: string | null) => {
        const mine = ++placeSeq.current
        if (!reduced) {
          const resting = snapToViewport(heroSnap.current)
          // No resting snapshot yet (the map just scrolled into view): read it now, once, at the user's action.
          const now = resting.length > 0 ? resting : captureDomBoxes(document.querySelector(MAP_SEL))
          pendingFrom.current = now.length > 0 ? now : null
        }
        const m = pills.find((x) => x.id === story)
        const warm = prefetchHeroTopic(qc, { id: story, topicId: m?.topicId ?? topicStories.stories[story]?.topicId ?? null, story: hasStory(story) }, code, c)
        void Promise.race([warm, new Promise((r) => window.setTimeout(r, 1200))]).then(() => {
          if (mine === placeSeq.current) onPlaceApply(code, c)
        })
      }
    : undefined
  // The topic word in the headline: a dropdown of the same pills as the chip row.
  const topicWord = topicDef ? (CAPTION_COPY[story]?.topic ?? topicDef.subject.toLowerCase()) : candidate ? candidate.name : dcTopic
  const topicControl = { value: story, options: storyTopicOptions(pills, story, topicWord), onPick: selectStory }
  // National: every state's own count, and each state's passages to quote (#1230): real public meetings only, meetings
  // where the public mostly opposed first, then newest first (the API's map-quote pick).
  const national = useQuery({
    queryKey: ['home', 'story-map', 'meeting-mentions', 'quotes-per-state', 3],
    queryFn: () => fetchDataCenterMeetingMentions({ quotesPerState: 3 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  // Speakers' own words with their recorded side, preferred over a meeting passage where a state has them.
  const speakers = useQuery({
    // Up to 3 quotes per state and side, named speakers ("Rob D.") first, so most states' cards can say who spoke.
    queryKey: ['home', 'story-map', 'positions', 'per-state', 3],
    queryFn: () => fetchDataCenterPositions({ limit: 10, perState: 3 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    const sides = speakers.data?.quotes
    for (const side of ['against', 'for', 'question'] as const) {
      for (const sq of sides?.[side] ?? []) {
        if (!sq.state_code || !sq.quote) continue
        pushQuote(out, sq.state_code, {
          place: [sq.jurisdiction_name, sq.state_code].filter(Boolean).join(', '),
          side,
          speakerName: sq.speaker_display_name ?? null,
          role: sq.speaker_role ?? null,
          item: sq.decision_headline ?? null,
          text: sq.quote,
          date: sq.meeting_date ?? null,
          meeting: null,
          url: sq.jump_url ?? sq.video_url ?? null,
          startSeconds: sq.start_seconds ?? null,
        })
      }
    }
    for (const m of national.data?.items ?? []) {
      if (!m.state_code || !m.evidence) continue
      pushQuote(out, m.state_code, {
        place: [m.jurisdiction_name, m.state_code].filter(Boolean).join(', '),
        text: m.evidence,
        date: m.meeting_date ?? null,
        meeting: m.meeting_title ?? null,
        stanceNote: dataCenterQuoteNote(m.ai_public_lean),
        url: m.jump_url ?? m.video_url ?? null,
        videoId: m.video_id ?? null,
        startSeconds: m.start_seconds ?? null,
        // Only when the record attributes the quoted words to a person (#1124): "First L." and the recorded role.
        speakerName: m.speaker_display_name ?? null,
        role: m.speaker_display_name ? (m.speaker_role ?? null) : null,
        summary: m.meeting_summary ?? null,
        analysisUrl: scopedMeetingHref(m.meeting_url, { state: stateCode ?? null, city: scope.city }),
      })
    }
    // At city level (#1285) the city's state shows only that city's passages: label and quotes move together.
    if (scope.city && scope.stateCode) {
      const c = scope.city.toLowerCase()
      out.set(scope.stateCode, (out.get(scope.stateCode) ?? []).filter((x) => x.place.toLowerCase().startsWith(c)))
    }
    return out
  }, [national.data, speakers.data, stateCode, scope.city, scope.stateCode])
  // At state (or city) scope the hero draws the story Overview's own state map (#1307): the state's counties with its
  // meeting towns, in the stance colours, from the same meeting-mentions place counts.
  const navigate = useNavigate()
  const statePlaces = useQuery({
    queryKey: ['home', 'story-map', 'meeting-mentions', 'state', scope.stateCode ?? ''],
    queryFn: () => fetchDataCenterMeetingMentions({ state: scope.stateCode, limit: 200 }),
    enabled: Boolean(scope.stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const byPlace = statePlaces.data?.counts?.by_place
  const stateAspect = useStateAspect(scope.stateCode)
  const drill = (city: string | null) => {
    if (!scope.stateCode) return
    if (mapWrapRef.current) {
      boxFlight.launch({
        source: mapWrapRef.current,
        focusGroup: city ?? scope.stateCode,
        targetSelector: '.stance-story [data-live], .stance-story [data-panel="0"]',
      })
    }
    const p = new URLSearchParams({ state: scope.stateCode, screen: 'overview' })
    if (city) p.set('city', city)
    navigate(`/stories/data-centers?${p.toString()}`)
  }
  // The map zooms to the state the story speaks for, the asked city marked where its record has a coordinate (#1285).
  const zoom = scope.stateCode
    ? {
        stateCode: scope.stateCode,
        pin: placeScope.pin,
        note: asked.city && placeScope.pinKnown && !placeScope.pin ? `No map location on record for ${asked.city}.` : null,
      }
    : null

  return (
    <section id="data-stories" aria-labelledby="home-story-dc" className="home-stories" style={{ scrollMarginTop: 72 }}>
      <div className="home-stories-inner">
        <HomeTopicBar pills={pills} selected={story} pendingId={pendingId} onSelect={selectStory} onPrefetch={(id) => void prefetch(id)} query={q} panelId="home-story-panel" scopeLabel={hot.yoy ? (hot.yoy.scope.city ? `${hot.yoy.scope.city}, ${hot.yoy.scope.state}` : (hot.yoy.scope.state ?? 'National')) : label} />
        <div id="home-story-panel" role="tabpanel" aria-labelledby={`home-tab-${story}`}>
        {resolving ? (
          <div className="home-story-card" aria-busy="true" style={{ minHeight: 320 }} />
        ) : candidate && hot.yoy ? (
          <HomeCandidateTopicCard key={candidate.slug} topic={candidate} yoy={hot.yoy} onPlaceApply={applyPlace} topicControl={topicControl} />
        ) : topicDef ? (
          <HomeTopicStoryCard def={topicDef} scope={asked} query={q} onPlaceApply={applyPlace} topicControl={topicControl} />
        ) : (
        <div className="home-story-card" key="data-centers">
          <div className="home-story-text">
            <p className="font-mono-x home-story-eyebrow">Data story · {STORY.title}</p>
            {/* While the record loads, the headline's place is held (invisible) so the question doesn't flash first. */}
            <h1 id="home-story-dc" className={`font-display home-story-headline${isLongTitle(dcTitle) ? ' is-long' : ''}`} aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
              {/* The place in the title is the place control (#1206): "[America ▾] hates data centers." */}
              <HomeStoryTitle caption={dcCaption} topic={dcTopic} scope={scope} onPlaceApply={applyPlace} topicControl={topicControl} />
            </h1>
            {/* The subhead speaks only for the caption's scope (#1134): never a national claim on a place's page. */}
            {!pending && <HomeStorySubhead caption={dcCaption} topic={dcTopic} scope={scope} onPlaceApply={applyPlace} subhead={dcSubhead} />}
            {dcCaption.basis && (
              <p className="home-story-basis">
                {dcCaption.basis}
              </p>
            )}
            {/* #1348: how many governments and meetings our recordings hold for the scope the counts speak for. */}
            {!pending && <CoverageLine scope={scope} className="home-story-coverage" />}
            {/* Next steps first (#1176): Start, Next story and the drill-down hint sit in the first screen. */}
            <div className="home-story-actions">
              <Link
                to={storyStartHref('data-centers', q)}
                className="home-story-start"
                onClick={() => {
                  if (mapWrapRef.current) {
                    boxFlight.launch({
                      source: mapWrapRef.current,
                      focusGroup: scope.stateCode ?? undefined,
                      targetSelector: '.stance-story [data-live], .stance-story [data-panel="0"]',
                    })
                  }
                }}
              >
                {storyStartLabel('data-centers', label)} <span aria-hidden="true">→</span>
              </Link>
            </div>
            <HomeStoryDrill
              slotRef={setCardSlot}
              hint={scope.stateCode && byPlace && byPlace.length > 0 ? 'Pick a county or a town on the map to open its story.' : undefined}
            />
          </div>

          <div className="home-story-map" ref={mapWrapRef}>
            {scope.stateCode && (statePlaces.isPending || (byPlace && byPlace.length > 0)) ? (
              byPlace && byPlace.length > 0 ? (
                <StoryCountyMap
                  stateCode={scope.stateCode}
                  scopeCity={asked.city}
                  scopeLabel={label}
                  byPlace={byPlace}
                  onPickState={(code) => applyPlace?.(code, null)}
                  passages={statePlaces.data?.items}
                  cardSlot={cardSlot}
                  onDrill={drill}
                  chrome={false}
                />
              ) : (
                <MapSkeleton aspect={stateAspect} label={`Loading the map of ${label}`} />
              )
            ) : national.isError ? (
              <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
            ) : (
              <StoryStatesMap
                byState={national.data?.counts?.by_state}
                quotes={quotes}
                stance={speakers.data?.available ? (speakers.data.by_state ?? []) : undefined}
                highlight={scope.stateCode ?? null}
                zoom={zoom}
                href={(code) => `/stories/data-centers?state=${encodeURIComponent(code)}&screen=overview`}
                cardSlot={cardSlot}
              />
            )}
          </div>
        </div>
        )}
        </div>

        {/* Story -> what happens next (#1302): below the story and its map; Coming up first. It follows the place asked in
            the URL (each card says when that place has nothing and offers the wider view). Topic switching is only the
            chip bar above (#1371); the large Browse topics strip is gone. */}
        {!candidate && !resolving && (
        <HomeOutcomesScroller
          topic={story}
          subject={topicDef ? (CAPTION_COPY[story]?.topic ?? topicDef.subject.toLowerCase()) : dcTopic}
          stateCode={stateCode ?? null}
          city={topicDef ? null : asked.city}
          label={topicDef ? (stateName ?? 'National') : storyScopeLabel(asked)}
          dataCenterStory={!topicDef}
        />
        )}
      </div>
    </section>
  )
}
