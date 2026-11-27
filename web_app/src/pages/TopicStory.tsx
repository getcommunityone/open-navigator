import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { fetchTopicCaptionFacts, fetchTopicMeetings, fetchTopicStanceMap, fetchTopicStates } from '../api/topics'
import { companySearchTerm } from '../utils/companySearchTerm'
import { topicStanceForMap } from '../utils/topicStance'
import { positionVerdict, spokeOf, topicPositions } from '../utils/topicPositions'
import {
  CAPTION_COPY,
  HATES_MIN_MEETINGS,
  captionSubhead,
  captionText,
  pickCaption,
  positionCounts,
  storyStartLabel,
  type Caption,
} from '../utils/storyCaption'
import { nextStoryLink } from '../utils/storyNav'
import { droppedNote, planTopicScreens, type ScreenAvailability, type TopicScreenId } from '../utils/topicStoryScreens'
import type { TopicStoryDef } from '../utils/topicStories'
import type { StoryScope } from '../utils/dataStory'
import { useTopicStories } from '../hooks/useTopicStories'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { useSwipeNav } from '../hooks/useSwipeNav'
import { highlightSnippet } from '../lib/highlight'
import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { NUDGE_ENTRANCE_MS } from '../utils/idleNudge'
import StoryStatesMap, { type StateQuote } from '../components/home/StoryStatesMap'
import TimelineChart from '../components/stance/TimelineChart'
import DumbbellChart from '../components/stance/DumbbellChart'
import FloatingNext from '../components/stance/FloatingNext'
import PlaceControl from '../components/stance/PlaceControl'
import ProgressPips from '../components/stance/ProgressPips'
import ScopeBar from '../components/stance/ScopeBar'
import SentenceHeading from '../components/stance/SentenceHeading'
import StoryScreenFrame from '../components/stance/StoryScreenFrame'
import TopicPositionsBreakdown from '../components/stance/TopicPositionsBreakdown'
import { NextStoryCard, StoryBottomBar } from '../components/stance/StoryProgress'
import { useStoryScreens } from '../components/stance/useStoryScreens'
import '../styles/folio.css'
import '../styles/stance.css'
import '../styles/story-actions.css'
import '../styles/topic-story.css'
import { HOUSE_STYLE } from '../utils/houseTheme'

/**
 * A topic story (#1013): one curated topic's meetings, told from the transcript record. Since #1224 it is told screen by
 * screen like the Data Center Story (the shared screen machine `useStoryScreens`, the same top bar, progress segments,
 * Back/Next, keys and swipe): a cover, then Overview (the state box map), Over time, Who spoke, Companies, What was said,
 * Decisions and a Recap. Every screen is built from data the topic has (utils/topicStoryScreens); one with nothing on record
 * for the place drops out and the cover says so. Everything shown is counted or quoted from `topic_transcript_link`, the AI
 * reading (`topic_meeting_lean`) and the decisions search for the topic.
 */
// The stories are derived from the topic catalog (#1133): every curated topic with linked meetings (utils/topicStories).

const fmt = (n: number) => n.toLocaleString('en-US')
const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
const meetingsWord = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`

interface PlatformCompany {
  master_org_id: string
  company_name: string
  aliases: string[]
  website_url: string | null
  meetings: number
  decisions: number
  newest: { title: string | null; date: string | null; jurisdiction_name: string | null; state_code: string | null; url: string | null; evidence: string | null } | null
}

interface DecisionResult {
  title: string
  subtitle?: string
  description?: string
  url?: string
}

const PAGE = 8
const COUNTED_FROM = /Counted from local meeting recordings/
const COUNTED_LINE = 'Counted from local meeting recordings and transcripts that mention the topic.'

const avail = (q: { isPending: boolean; isError: boolean }, has: () => boolean): ScreenAvailability =>
  q.isPending ? 'loading' : q.isError ? 'error' : has() ? 'ready' : 'empty'

/** Resolves the story from the topic catalog, then tells it; keyed by the topic so another topic starts fresh. */
export default function TopicStory({ slug: slugProp }: { slug?: string }) {
  const params = useParams<{ storyId?: string }>()
  const topicStories = useTopicStories()
  const def = topicStories.stories[slugProp ?? params.storyId ?? '']
  if (!def && topicStories.pending) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16" aria-busy="true">
        <p className="text-stone-500">Loading the story…</p>
      </div>
    )
  }
  if (!def) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <p className="text-stone-700">{topicStories.failed ? 'This story could not be loaded right now.' : "That story isn't available."}</p>
        <Link to="/stories" className="text-teal-700 underline">
          See all data stories
        </Link>
      </div>
    )
  }
  return <TopicStoryScreens key={def.slug} def={def} live={topicStories.live} />
}

function TopicStoryScreens({ def, live }: { def: TopicStoryDef; live: ReturnType<typeof useTopicStories>['live'] }) {
  const [sp, setSp] = useSearchParams()
  const navigate = useNavigate()
  const reduced = usePrefersReducedMotion()
  const raw = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(raw) ? raw : null
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const label = stateName ?? 'National'
  // The scope every story link carries: this page is at state grain (it shows and queries the state only), so its links
  // carry the state it shows, never a city its label doesn't name (CLAUDE.md, scope label rule; city grain is #1186).
  const scopeQ = stateCode ? `?state=${stateCode}` : ''
  const scope: StoryScope = useMemo(() => ({ stateCode: stateCode ?? undefined, stateName, city: null }), [stateCode, stateName])
  const screenParam = sp.get('screen') ?? ''
  const subject = def.subject.toLowerCase()
  const topicWord = CAPTION_COPY[def.slug]?.topic ?? subject
  const words = topicPositions(def.slug)

  // A city picked in the place dialog: topic stories are drawn by state (#1186), so its state applies and the cover says so.
  const [cityAsked, setCityAsked] = useState<string | null>(null)
  const [placeOpen, setPlaceOpen] = useState(false)
  const [atEnd, setAtEnd] = useState(false)
  const applyPlace = useCallback(
    (code: string | null, community: string | null) => {
      setCityAsked(code && community ? community : null)
      setSp(
        (prev) => {
          const n = new URLSearchParams(prev)
          if (code) n.set('state', code)
          else n.delete('state')
          n.delete('city')
          return n
        },
        { replace: true },
      )
    },
    [setSp],
  )

  // The map always shows the whole country (each state its own count); the headline and lists follow the scope.
  const national = useQuery({
    queryKey: ['topic-story', def.topicId, 'states'],
    queryFn: () => fetchTopicStates(def.topicId),
    staleTime: 5 * 60_000,
  })
  // The four-colour split (#1127): the AI reading of each state's meetings, national like the map.
  const stanceQ = useQuery({
    queryKey: ['topic-story', def.topicId, 'state-map'],
    queryFn: () => fetchTopicStanceMap(def.topicId),
    staleTime: 5 * 60_000,
  })
  const stance = useMemo(() => topicStanceForMap(stanceQ.data), [stanceQ.data])
  // The headline's facts (#1125), keyed on the scope so the label and the numbers move together.
  const captionQ = useQuery({
    queryKey: ['caption-facts', def.slug, stateCode ?? ''],
    queryFn: () => fetchTopicCaptionFacts(def.slug, stateCode ?? undefined),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    for (const m of national.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      const list = out.get(m.state_code) ?? []
      if (!out.has(m.state_code)) out.set(m.state_code, list)
      list.push({
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        url: m.video_url ?? null,
        videoId: m.video_id ?? null,
      })
    }
    return out
  }, [national.data])
  const meetings = useInfiniteQuery({
    queryKey: ['topic-story', def.topicId, 'meetings', stateCode ?? ''],
    queryFn: ({ pageParam }) => fetchTopicMeetings(def.topicId, { state: stateCode ?? undefined, limit: PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const seen = pages.reduce((a, p) => a + p.items.length, 0)
      return seen < last.total ? seen : undefined
    },
  })
  const decisions = useQuery({
    queryKey: ['topic-story', def.topicId, 'decisions', stateCode ?? ''],
    queryFn: async () => {
      const res = await api.get('/search', {
        params: { types: 'decisions', topic_id: def.topicId, limit: 6, sort: 'date_desc', ...(stateCode ? { state: stateCode } : {}) },
      })
      return {
        total: (res.data?.type_totals?.decisions as number | undefined) ?? 0,
        items: (res.data?.results?.decisions ?? []) as DecisionResult[],
      }
    },
  })
  // The platform companies named in this scope's meetings and decisions (#1015).
  const companies = useQuery({
    queryKey: ['topic-story', def.topicId, 'companies', stateCode ?? ''],
    queryFn: async () =>
      ((await api.get(def.companiesPath!, { params: stateCode ? { state: stateCode } : {} })).data?.companies ?? []) as PlatformCompany[],
    enabled: Boolean(def.companiesPath),
    staleTime: 5 * 60_000,
  })

  // --- which screens the place has ---------------------------------------------------------------------------------------
  const facts = captionQ.data
  const meetingCount = facts?.meetings ?? 0
  const counts = useMemo(() => positionCounts(facts, facts?.meetings), [facts])
  const items = meetings.data?.pages.flatMap((p) => p.items) ?? []
  const total = meetings.data?.pages[0]?.total ?? 0
  const named = (companies.data ?? []).filter((c) => c.meetings + c.decisions > 0)
  const availability: Partial<Record<TopicScreenId, ScreenAvailability>> = {
    timeline: avail(captionQ, () => meetingCount > 0),
    positions: avail(captionQ, () => counts != null),
    companies: def.companiesPath ? avail(companies, () => named.length > 0) : 'absent',
    said: avail(meetings, () => total > 0),
    decided: avail(decisions, () => (decisions.data?.total ?? 0) > 0),
  }
  const availKey = JSON.stringify(availability)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const plan = useMemo(() => planTopicScreens(availability), [availKey])
  const screens = plan.screens
  const n = screens.length
  const keepKey = screens.map((s) => s.id).join()

  const { rootRef, startRef, wide, mode, active, activeRef, onCover, goTo, next, prev } = useStoryScreens({
    screens,
    screenParam,
    setSp,
    scopeKey: stateCode ?? '',
    resetKey: def.slug,
    dialogOpen: placeOpen,
    reduced,
  })
  useIdleNudge({ rootRef, screen: `[data-panel="${active}"]`, resetKey: active, entranceMs: NUDGE_ENTRANCE_MS })
  // Phone swipe (#1224): left for the next screen, right for the previous; from the cover a swipe opens the first screen.
  useSwipeNav({
    rootRef,
    onNext: () => (onCover ? goTo(0) : next()),
    onPrev: () => (onCover ? undefined : prev()),
    enabled: !placeOpen,
  })

  // --- the title --------------------------------------------------------------------------------------------------------
  const caption: Caption = pickCaption(def.slug, facts, scope)
  const noMeetings = captionQ.isSuccess && facts?.meetings === 0
  // Place first at a place scope: "California has no meetings on record about pickleball."
  const template: Caption['template'] = noMeetings
    ? stateName
      ? [{ blank: 'place' }, ' has no meetings on record about ', { blank: 'topic' }, '.']
      : ['No meetings on record about ', { blank: 'topic' }, ' across ', { blank: 'place' }, ' yet.']
    : caption.template
  const placeDisplay = noMeetings ? (stateName ?? 'America') : caption.place
  const headline = noMeetings
    ? stateName
      ? `${stateName} has no meetings on record about ${topicWord}.`
      : `No meetings on record about ${topicWord} yet.`
    : captionText(caption, topicWord)
  const subhead = noMeetings ? null : captionSubhead(caption, def.slug, scope)
  const basis = caption.basis
  const onward = nextStoryLink(def.slug, scopeQ, live)
  const note = droppedNote(plan.dropped, label)
  const labels = screens.map((s) => s.eyebrow)

  // --- each screen's words and figure -----------------------------------------------------------------------------------
  const loadingOr = (q: { isPending: boolean; isError: boolean }, what: string, ready: () => string) =>
    q.isPending ? `Loading ${what}…` : q.isError ? `The ${what} could not be loaded right now.` : ready()
  const verdict = counts ? positionVerdict(counts, HATES_MIN_MEETINGS[stateCode ? 'state' : 'national']) : null
  const where = stateName ? `in ${stateName}` : 'nationally'
  const decisionsSearch = `/search?types=decisions&topic_id=${def.topicId}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`

  const screen = (id: TopicScreenId): { headline: string; context: ReactNode; right: ReactNode } => {
    switch (id) {
      case 'overview':
        return {
          headline: captionQ.isPending ? def.title : headline,
          context: basis ?? COUNTED_LINE,
          right: (
            <>
              {national.isError ? (
                <p className="stance-nodata" role="status">
                  The map could not be loaded right now.
                </p>
              ) : (
                <StoryStatesMap
                  byState={national.data?.states}
                  quotes={quotes}
                  highlight={stateCode}
                  href={(code) => `/stories/${def.slug}?state=${encodeURIComponent(code)}&screen=overview`}
                  subject={subject}
                  stance={stance}
                  stanceUnit="meetings"
                  positions={words}
                />
              )}
              <p className="stance-note">
                Drawn by state{stateName ? `, ${stateName} at full strength` : ''}: choose a state to narrow the story to it. Topic
                meetings are not counted by county yet, so there is no county view.
              </p>
            </>
          ),
        }
      case 'timeline':
        return {
          headline: loadingOr(captionQ, 'meeting counts', () => `${meetingsWord(meetingCount)} ${where} took up ${topicWord}.`),
          context: 'Meetings per year whose transcript mentions the topic, and how the latest period compares with the one before.',
          right: (
            <div className="topic-story-charts">
              <TimelineChart topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} idBase={`topic-${def.slug}`} />
              <DumbbellChart topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} idBase={`topic-${def.slug}`} />
            </div>
          ),
        }
      case 'positions': {
        const spoke = counts ? spokeOf(counts) : 0
        const h = loadingOr(captionQ, 'AI reading', () =>
          !verdict || !counts
            ? 'No AI reading of these meetings yet.'
            : spoke === 0
              ? `In all ${meetingsWord(counts.read)} the AI read ${where}, the public didn't speak on ${topicWord}.`
              : verdict.kind === 'majority'
              ? `${stateName ? `In ${stateName}` : 'Across America'}, the public ${verdict.side === 'against' ? words.againstVerb : words.forVerb} in ${fmt(verdict.count)} of ${meetingsWord(verdict.of)} where it spoke.`
              : verdict.kind === 'split'
                ? `${stateName ?? 'America'} is split on ${topicWord}: no side has most of the ${meetingsWord(verdict.of)} where the public spoke.`
                : `Too few meetings where the public spoke ${where} to say which way it leans (${fmt(spoke)}).`,
        )
        return {
          headline: h,
          context: "An AI read each meeting's transcript for the public's position. These are meetings, never counted speakers.",
          right: counts ? <TopicPositionsBreakdown counts={counts} words={words} scopeLabel={label} labelledBy="story-h-positions" /> : null,
        }
      }
      case 'companies':
        return {
          headline: loadingOr(
            companies,
            'companies',
            () => `${fmt(named.length)} ${named.length === 1 ? 'company was' : 'companies were'} named in ${stateName ? `${stateName}'s` : 'these'} meetings and decisions.`,
          ),
          context: 'The rental platforms named in the record, counted from it.',
          right: companies.data ? (
            <ul className="topic-story-list">
              {companies.data.map((c) => {
                const brands = c.aliases.filter((a) => a !== c.company_name && !a.includes(','))
                return (
                  <li key={c.master_org_id} className="topic-story-item">
                    <p className="topic-story-item-title">
                      <Link to={`/organizations/${encodeURIComponent(c.master_org_id)}`}>{c.company_name}</Link>
                    </p>
                    {brands.length > 0 && <p className="topic-story-item-meta">{brands.join(', ')}</p>}
                    {c.meetings + c.decisions === 0 ? (
                      <p className="topic-story-item-meta">Not named in {label === 'National' ? 'any meeting on record' : `${label}'s meetings on record`}.</p>
                    ) : (
                      <p className="topic-story-item-body">
                        <Link to={`/search?q=${encodeURIComponent(companySearchTerm(c.company_name, c.newest?.evidence))}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`}>
                          {meetingsWord(c.meetings)}
                        </Link>
                        {' · '}
                        {fmt(c.decisions)} {c.decisions === 1 ? 'decision' : 'decisions'}
                      </p>
                    )}
                    {c.newest?.evidence && (
                      <blockquote className="topic-story-quote">
                        “{highlightSnippet(c.newest.evidence)}”
                        <footer>
                          {[c.newest.jurisdiction_name, c.newest.state_code].filter(Boolean).join(', ')}
                          {fmtDate(c.newest.date) ? ` · ${fmtDate(c.newest.date)}` : ''}
                          {c.newest.url && (
                            <>
                              {' · '}
                              {c.newest.url.startsWith('/') ? (
                                <Link to={c.newest.url}>Open</Link>
                              ) : (
                                <a href={c.newest.url} target="_blank" rel="noopener noreferrer">
                                  Watch ↗
                                </a>
                              )}
                            </>
                          )}
                        </footer>
                      </blockquote>
                    )}
                  </li>
                )
              })}
            </ul>
          ) : null,
        }
      case 'said':
        return {
          headline: loadingOr(meetings, 'meetings', () => `What was said in ${meetingsWord(total)} ${where}.`),
          context: 'Newest first. Each passage is quoted from the meeting transcript.',
          right: (
            <>
              <ul className="topic-story-list">
                {items.map((m) => (
                  <li key={m.video_id} className="topic-story-item">
                    <p className="topic-story-item-title">{m.title ?? 'Meeting'}</p>
                    <p className="topic-story-item-meta">
                      {[m.jurisdiction_name ?? m.city, m.state].filter(Boolean).join(', ')}
                      {fmtDate(m.date) ? ` · ${fmtDate(m.date)}` : ''}
                    </p>
                    {m.excerpt && <blockquote className="topic-story-quote">“{highlightSnippet(m.excerpt)}”</blockquote>}
                    {m.video_url && (
                      <a href={m.video_url} target="_blank" rel="noopener noreferrer" className="topic-story-link">
                        Watch the meeting ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
              {meetings.hasNextPage && (
                <button type="button" className="folio-btn" onClick={() => meetings.fetchNextPage()} disabled={meetings.isFetchingNextPage}>
                  {meetings.isFetchingNextPage ? 'Loading…' : 'Show more meetings'}
                </button>
              )}
            </>
          ),
        }
      case 'decided': {
        const d = decisions.data
        return {
          headline: loadingOr(decisions, 'decisions', () => `${fmt(d!.total)} ${d!.total === 1 ? 'decision' : 'decisions'} ${where} mention ${topicWord}.`),
          context: 'Decisions whose record mentions the topic, newest first.',
          right: d ? (
            <>
              <ul className="topic-story-list">
                {d.items.map((x, i) => (
                  <li key={x.url ?? i} className="topic-story-item">
                    {x.url ? (
                      <Link to={x.url} className="topic-story-item-title">
                        {x.title}
                      </Link>
                    ) : (
                      <p className="topic-story-item-title">{x.title}</p>
                    )}
                    {x.subtitle && <p className="topic-story-item-meta">{x.subtitle}</p>}
                    {x.description && <p className="topic-story-item-body">{highlightSnippet(x.description)}</p>}
                  </li>
                ))}
              </ul>
              {d.total > d.items.length && (
                <Link to={decisionsSearch} className="topic-story-link">
                  See all {fmt(d.total)} decisions →
                </Link>
              )}
            </>
          ) : null,
        }
      }
      case 'recap': {
        const parts = [
          captionQ.isSuccess ? meetingsWord(meetingCount) : null,
          decisions.isSuccess ? `${fmt(decisions.data.total)} ${decisions.data.total === 1 ? 'decision' : 'decisions'}` : null,
          def.companiesPath && companies.isSuccess ? `${fmt(named.length)} ${named.length === 1 ? 'company' : 'companies'} named` : null,
        ].filter((x): x is string => x != null)
        return {
          headline: `That's the record on ${topicWord} ${stateName ? `in ${stateName}` : 'across America'}.`,
          context: parts.length ? `${parts.join(', ')}, from local meeting recordings and transcripts.` : COUNTED_LINE,
          right: (
            <ul className="topic-story-onward">
              {(decisions.data?.total ?? 0) > 0 && (
                <li>
                  <Link to={decisionsSearch}>Every decision on {topicWord} →</Link>
                </li>
              )}
              <li>
                <Link to={`/browse-topics${scopeQ}`}>Browse every topic{stateName ? ` in ${stateName}` : ''} →</Link>
              </li>
              <li>
                <Link to={`/stories${scopeQ}`}>All data stories →</Link>
              </li>
            </ul>
          ),
        }
      }
    }
  }

  return (
    <div
      className="folio stance-game stance-story topic-story"
      style={HOUSE_STYLE}
      ref={rootRef}
      data-mode={mode}
      data-fade={reduced ? '' : undefined}
      data-sbar={wide ? undefined : ''}
    >
      <ScopeBar
        backTo={`/stories${scopeQ}`}
        backLabel="← Data stories"
        title={def.title}
        label={label}
        heading={
          <SentenceHeading
            template={template}
            blanks={[
              {
                id: 'place',
                label: 'Place',
                value: stateCode ?? '',
                display: placeDisplay,
                options: [],
                onChange: () => {},
                control: (
                  <PlaceControl
                    variant="blank"
                    display={placeDisplay}
                    stateCode={stateCode ?? undefined}
                    city={null}
                    open={placeOpen}
                    onOpenChange={setPlaceOpen}
                    onApply={applyPlace}
                  />
                ),
              },
              {
                id: 'topic',
                label: 'Topic',
                value: def.slug,
                display: topicWord,
                // The current topic reads as the sentence says it; the others by their story names.
                options: live.map((s) => ({ value: s.id, label: s.id === def.slug ? topicWord : s.title })),
                onChange: (v) => navigate(`/stories/${encodeURIComponent(v)}${scopeQ}`),
              },
            ]}
          />
        }
        stateCode={stateCode ?? undefined}
        stateName={stateName}
        city={null}
        current={screens[active]?.eyebrow ?? ''}
        progress={wide ? <ProgressPips count={n} active={active} labels={labels} onJump={goTo} /> : undefined}
        placeOpen={placeOpen}
        onPlaceOpenChange={setPlaceOpen}
        onApply={applyPlace}
      />
      {/* The cover (#1182), as on the Data Center Story: subhead, basis, the two story buttons, then what the story leaves out. */}
      <div className="stance-intro" data-cover>
        {subhead && <p className="stance-title-subhead">{subhead}</p>}
        {basis && <p className="stance-title-basis">{basis}</p>}
        <p className="stance-title-subhead topic-story-lede">{def.lede}</p>
        <div className="home-story-actions">
          <button type="button" className="home-story-start" ref={startRef} onClick={() => goTo(0)}>
            {storyStartLabel(def.slug, label, def.subject)} <span aria-hidden="true">→</span>
          </button>
          <Link to={onward.href} className="home-story-next">
            {onward.label} <span aria-hidden="true">→</span>
          </Link>
        </div>
        {!captionQ.isPending && !COUNTED_FROM.test(basis ?? '') && <p className="stance-note">{COUNTED_LINE}</p>}
        {cityAsked && stateName && (
          <p className="stance-note" role="status">
            Topic stories are drawn by state, so this shows all of {stateName}; {cityAsked} on its own isn't available yet.
          </p>
        )}
        {note && <p className="stance-note">{note}</p>}
      </div>
      <p className="folio-sr-only" aria-live="polite">
        {screens[active] ? `${screens[active]!.eyebrow}. ${screen(screens[active]!.id).headline}` : ''}
      </p>
      <div className="stance-body">
        {/* Keyed by which screens are in the story: the pinned layout moves screens into its own wrappers (see DataStory). */}
        <div className="stance-acts" key={keepKey}>
          {screens.map((s, i) => {
            const v = screen(s.id)
            const last = i === n - 1
            return (
              <StoryScreenFrame
                key={s.id}
                id={s.id}
                index={i}
                active={active === i}
                eyebrow={s.eyebrow}
                headline={v.headline}
                context={v.context}
                nextLabel={last ? null : screens[i + 1]!.eyebrow}
                onNext={() => goTo(i + 1)}
                onPrev={i > 0 ? () => goTo(i - 1) : undefined}
                navPrimary={
                  last ? (
                    <Link className="folio-btn stance-next stance-next-end" to={onward.href} data-primary data-nav="next">
                      {onward.next ? 'Next story' : 'All stories'} <span aria-hidden="true">→</span>
                    </Link>
                  ) : undefined
                }
                right={v.right}
              />
            )
          })}
        </div>
        <NextStoryCard href={onward.href} label={onward.label} isStory={onward.next != null} onInView={setAtEnd} />
      </div>
      {wide ? (
        !atEnd && !onCover && <FloatingNext rootRef={rootRef} screen={`[data-panel="${active}"]`} />
      ) : (
        <StoryBottomBar
          active={active}
          count={n}
          nextLabel={active < n - 1 ? (screens[active + 1]?.eyebrow ?? null) : null}
          onNext={() => goTo(Math.min(activeRef.current + 1, n - 1))}
          storyHref={onward.href}
          storyLabel={onward.label}
          storyIsNext={onward.next != null}
          hideNext={onCover}
        />
      )}
      <p className="stance-keys">Keys: → or PageDown next · ← or PageUp back · Home and End jump to the ends · on a phone, swipe left or right</p>
    </div>
  )
}
