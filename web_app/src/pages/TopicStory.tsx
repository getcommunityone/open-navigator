import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { fetchTopicCaptionFacts, fetchTopicDecisions, fetchTopicMeetings, fetchTopicStanceMap, fetchTopicStates } from '../api/topics'
import { decisionsSummary, saidSummary } from '../utils/saidCards'
import { DecisionPanel, SaidQuoteCard } from '../components/stance/TopicRecordCards'
import { companySearchTerm } from '../utils/companySearchTerm'
import { topicStanceForMap } from '../utils/topicStance'
import { positionVerdict, quoteStanceNote, spokeOf, topicPositions } from '../utils/topicPositions'
import {
  CAPTION_COPY,
  HATES_MIN_MEETINGS,
  captionSubhead,
  pickCaption,
  positionCounts,
  withTopicBlank,
  type Caption,
} from '../utils/storyCaption'
import { storyCloseHref, storyStartHref, storyTopicOptions } from '../utils/storyNav'
import { droppedNote, planTopicScreens, type ScreenAvailability, type TopicScreenId } from '../utils/topicStoryScreens'
import type { TopicStoryDef } from '../utils/topicStories'
import type { StoryScope } from '../utils/dataStory'
import { useTopicStories } from '../hooks/useTopicStories'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { highlightSnippet } from '../lib/highlight'
import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { NUDGE_ENTRANCE_MS } from '../utils/idleNudge'
import { useStoryScope } from '../hooks/useStoryScope'
import StoryStatesMap, { type StateQuote } from '../components/home/StoryStatesMap'
import TimelineChart from '../components/stance/TimelineChart'
import DumbbellChart from '../components/stance/DumbbellChart'
import PlaceControl from '../components/stance/PlaceControl'
import ProgressPips from '../components/stance/ProgressPips'
import StoryClose from '../components/stance/StoryClose'
import ScopeBar from '../components/stance/ScopeBar'
import { StoryBottomBar } from '../components/stance/StoryProgress'
import SentenceHeading from '../components/stance/SentenceHeading'
import StoryScreenFrame from '../components/stance/StoryScreenFrame'
import TopicPositionsBreakdown from '../components/stance/TopicPositionsBreakdown'
import StoryNextButton from '../components/stance/StoryNextButton'
import { useStoryScreens } from '../components/stance/useStoryScreens'
import LegislationMap from '../components/stance/LegislationMap'
import LocalActionsTracker from '../components/stance/LocalActionsTracker'
import PositionBreakdown from '../components/stance/PositionBreakdown'
import { fetchTopicLegislation, fetchTopicLocalActions } from '../api/topicPolicy'
import UpcomingPanel from '../components/stance/UpcomingPanel'
import { useTopicUpcoming } from '../hooks/useTopicUpcoming'
import { upcomingHeadline } from '../utils/topicUpcoming'
import OutcomesChain from '../components/stance/OutcomesChain'
import { useTopicOutcomes } from '../hooks/useTopicOutcomes'
import { outcomesHeadline } from '../utils/topicOutcomes'
import { actionLabels, shadeStates, STATUS_LABEL, yearSpan } from '../utils/topicPolicy'
import '../styles/folio.css'
import '../styles/stance.css'
import '../styles/story-actions.css'
import '../styles/topic-story.css'
import { HOUSE_STYLE } from '../utils/houseTheme'

/**
 * A topic story (#1013): one curated topic's meetings, told from the transcript record. Since #1224 it is told screen by
 * screen like the Data Center Story (the shared screen machine `useStoryScreens`, the same top bar, progress segments,
 * Back/Next, keys and swipe): a cover, then Overview (the state box map), Over time, Who spoke, State bills, Votes (#1274),
 * Companies, What was said,
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
/** "were against the courts" -> "was against the courts"; "mostly opposed it" -> "opposed <topic>" (after "the public mostly"). */
const publicVerb = (verb: string, topic: string) => verb.replace(/^were /, 'was ').replace(/^mostly /, '').replace(/ it$/, ` ${topic}`)
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
  const askedState = STATE_CODES.includes(raw) ? raw : null
  // A state with fewer than 5 meetings on the topic steps up to the country, and says why (#1285, `useStoryScope`).
  // Topic stories are drawn by state (#1186), so a city asked is handled by the cover's note below, not here.
  const placeScope = useStoryScope(def.slug, CAPTION_COPY[def.slug]?.topic ?? def.subject.toLowerCase(), askedState, null)
  const stateCode = placeScope.effective.stateCode ?? null
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
  // A deep link with ?city= gets the same note (the page shows its state only).
  const [cityAsked, setCityAsked] = useState<string | null>(() => (stateCode ? (sp.get('city') ?? '').trim() || null : null))
  const [placeOpen, setPlaceOpen] = useState(false)
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
        // Where the public stood at the quoted meeting (#1230): the API picks a meeting where it took a side first.
        stanceNote: quoteStanceNote(def.slug, topicWord, m.public_stance),
        url: m.video_url ?? null,
        videoId: m.video_id ?? null,
        // Named only where the speaker introduced themselves on the record (#1231).
        speakerName: m.speaker_display_name ?? null,
        role: m.speaker_display_name ? (m.speaker_role ?? null) : null,
      })
    }
    return out
  }, [national.data, def.slug, topicWord])
  const meetings = useInfiniteQuery({
    // People first (#1293): meetings where the public took a position, then a vote or a named person, then the rest.
    queryKey: ['topic-story', def.topicId, 'meetings', stateCode ?? '', 'people'],
    queryFn: ({ pageParam }) =>
      fetchTopicMeetings(def.topicId, { state: stateCode ?? undefined, limit: PAGE, offset: pageParam, sort: 'people' }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const seen = pages.reduce((a, p) => a + p.items.length, 0)
      return seen < last.total ? seen : undefined
    },
  })
  // Decisions on the topic and ones that only mention it (#1293): a keyword hit is not a decision on the topic.
  const decisions = useQuery({
    queryKey: ['topic-story', def.topicId, 'decisions', stateCode ?? '', 'split'],
    queryFn: () => fetchTopicDecisions(def.topicId, { state: stateCode ?? undefined, limit: 6 }),
  })
  // The platform companies named in this scope's meetings and decisions (#1015).
  const companies = useQuery({
    queryKey: ['topic-story', def.topicId, 'companies', stateCode ?? ''],
    queryFn: async () =>
      ((await api.get(def.companiesPath!, { params: stateCode ? { state: stateCode } : {} })).data?.companies ?? []) as PlatformCompany[],
    enabled: Boolean(def.companiesPath),
    staleTime: 5 * 60_000,
  })

  // State bills (#1274): national counts (the map shows every state; the scoped state is outlined and opened). Same query
  // keys as LegislationMap / LocalActionsTracker, so the screen and its chart share one request.
  const legislation = useQuery({
    queryKey: ['topic-legislation', def.slug],
    queryFn: () => fetchTopicLegislation(def.slug),
    staleTime: 10 * 60_000,
    retry: 1,
  })
  const localActions = useQuery({
    queryKey: ['topic-local-actions', def.slug, stateCode ?? 'national'],
    queryFn: () => fetchTopicLocalActions(def.slug, stateCode ?? undefined),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  // What's coming up (#1302): the same query (and cache entry) as the screen's panel.
  const upcoming = useTopicUpcoming(def.slug, stateCode, null)
  // What happened next (#1314): the chain's counts, shared with the screen's panel.
  const outcomes = useTopicOutcomes(def.slug, stateCode, null)

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
    bills: avail(legislation, () => (legislation.data?.total_bills ?? 0) > 0),
    actions: avail(localActions, () => (localActions.data?.total ?? 0) > 0),
    companies: def.companiesPath ? avail(companies, () => named.length > 0) : 'absent',
    said: avail(meetings, () => total > 0),
    decided: avail(decisions, () => (decisions.data?.total ?? 0) > 0),
  }
  const availKey = JSON.stringify(availability)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const plan = useMemo(() => planTopicScreens(availability), [availKey])
  // The same array while the same screens are in the story: a screen's data going from loading to ready must not count as
  // a new set of screens (that re-lands the page and can swallow a move made meanwhile, as DataStory keys on keepKey).
  const keepKey = plan.screens.map((s) => s.id).join()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const screens = useMemo(() => plan.screens, [keepKey])
  const n = screens.length

  // The screen machine shared with the Data Center Story: landing, ?screen=, keys, the sideways swipe and re-aimed jumps.
  const { rootRef, wide, mode, active, activeRef, goTo } = useStoryScreens({
    screens,
    screenParam,
    setSp,
    scopeKey: stateCode ?? '',
    resetKey: def.slug,
    dialogOpen: placeOpen,
    reduced,
  })
  useIdleNudge({ rootRef, screen: `[data-panel="${active}"]`, resetKey: active, entranceMs: NUDGE_ENTRANCE_MS })

  // --- the title --------------------------------------------------------------------------------------------------------
  const caption: Caption = pickCaption(def.slug, facts, scope)
  const noMeetings = captionQ.isSuccess && facts?.meetings === 0
  // Place first at a place scope: "California has no meetings on record about pickleball."
  const template: Caption['template'] = noMeetings
    ? stateName
      ? [{ blank: 'place' }, ' has no meetings on record about ', { blank: 'topic' }, '.']
      : ['No meetings on record about ', { blank: 'topic' }, ' across ', { blank: 'place' }, ' yet.']
    : caption.template
  // The topic is always a control in the title (#1224), even when the conclusion's words don't name it.
  const titleTemplate = withTopicBlank(template, topicWord)
  const placeDisplay = noMeetings ? (stateName ?? 'America') : caption.place
  const subhead = noMeetings ? null : captionSubhead(caption, def.slug, scope)
  const basis = caption.basis
  // Close and the last screen's Done go home, keeping the scope (owner 2026-11-27: readers pick the next story there).
  const homeHref = storyCloseHref(def.slug, scopeQ)
  const note = droppedNote(plan.dropped, label)
  const labels = screens.map((s) => s.eyebrow)

  // --- each screen's words and figure -----------------------------------------------------------------------------------
  const loadingOr = (q: { isPending: boolean; isError: boolean }, what: string, ready: () => string) =>
    q.isPending ? `Loading ${what}…` : q.isError ? `The ${what} could not be loaded right now.` : ready()
  const verdict = counts ? positionVerdict(counts, HATES_MIN_MEETINGS[stateCode ? 'state' : 'national']) : null
  const where = stateName ? `in ${stateName}` : 'nationally'
  const decisionsSearch = `/search?types=decisions&topic_id=${def.topicId}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`

  const screen = (id: TopicScreenId): { headline: string; context: ReactNode; right: ReactNode; lead?: ReactNode } => {
    switch (id) {
      case 'overview':
        return {
          // Never the header title again (owner 2026-11-26): the Overview says what the map shows.
          // A chosen state is the story's place (#1316): the headline names it, never "state by state".
          headline: stateName ? `Where ${topicWord} came up in ${stateName}.` : `Where ${topicWord} came up, state by state.`,
          context: basis ?? COUNTED_LINE,
          // The opening's subhead, lede and notes (#1282) sit in the left column under the headline: Overview is screen 1.
          lead: (
            <div className="stance-overview-lead">
              {subhead && <p className="stance-title-subhead">{subhead}</p>}
              <p className="stance-title-subhead topic-story-lede">{def.lede}</p>
              {!captionQ.isPending && !COUNTED_FROM.test(basis ?? '') && basis != null && <p className="stance-note">{COUNTED_LINE}</p>}
              {cityAsked && stateName && (
                <p className="stance-note" role="status">
                  Topic stories are drawn by state, so this shows all of {stateName}; {cityAsked} on its own isn't available yet.
                </p>
              )}
              {note && <p className="stance-note">{note}</p>}
            </div>
          ),
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
                  // A chosen state is drawn as that state, never the national map (#1316, owner 27 Nov 2026).
                  zoom={stateCode ? { stateCode } : null}
                  href={(code) => `/stories/${def.slug}?state=${encodeURIComponent(code)}&screen=overview`}
                  subject={subject}
                  stance={stance}
                  stanceUnit="meetings"
                  positions={words}
                />
              )}
              <p className="stance-note">
                {stateName
                  ? `${stateName} only. Topic meetings are not counted by county yet, so the state is drawn whole; choose National in the header to compare states.`
                  : 'Drawn by state: choose a state to narrow the story to it.'}
              </p>
            </>
          ),
        }
      case 'upcoming':
        return {
          headline: loadingOr(upcoming, 'upcoming list', () => upcomingHeadline(upcoming.data, topicWord, label)),
          context:
            'Scheduled meetings and public hearings from today on, with the agenda, livestream or notice to take part, and the state bills still open. Nothing here is estimated.',
          right: (
            <UpcomingPanel
              topic={def.slug}
              stateCode={stateCode}
              scopeLabel={label}
              subject={subject}
              basePath={`/stories/${def.slug}`}
            />
          ),
        }
      case 'outcomes': {
        const w = actionLabels(def.slug)
        return {
          headline: loadingOr(outcomes, 'outcomes', () => outcomesHeadline(outcomes.data, topicWord, label)),
          context:
            'From the meetings where it came up to what the public said, what local bodies did, the state bills and what is next. Tap a step to see its records.',
          right: (
            <OutcomesChain
              topic={def.slug}
              stateCode={stateCode}
              scopeLabel={label}
              subject={subject}
              actionWords={{ advanced: w.advanced, blocked: w.blocked }}
              dataCenterStory={false}
              onOpenScreen={(id) => {
                const i = screens.findIndex((x) => x.id === id)
                if (i >= 0) goTo(i)
              }}
            />
          ),
        }
      }
      case 'timeline':
        return {
          headline: `How often ${topicWord} came up ${stateName ? `in ${stateName}` : 'across America'}, year by year.`,
          context: loadingOr(
            captionQ,
            'meeting counts',
            () => `${meetingsWord(meetingCount)} on record whose transcript mentions the topic, per year, and how the latest period compares with the one before.`,
          ),
          right: (
            <div className="topic-story-charts">
              <TimelineChart topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} idBase={`topic-${def.slug}`} />
              <DumbbellChart topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} idBase={`topic-${def.slug}`} />
            </div>
          ),
        }
      case 'positions': {
        const spoke = counts ? spokeOf(counts) : 0
        const placeWord = stateName ?? 'America'
        // A short conclusion, no counts (owner 2026-11-26); the numbers are in the line under it and the bars.
        const h = loadingOr(captionQ, 'who spoke', () =>
          !verdict || !counts
            ? `No position of the public is on record for these meetings yet.`
            : spoke === 0
              ? `The public didn't speak on ${topicWord} in the meetings read ${where}.`
              : verdict.kind === 'majority'
                ? `${stateName ? `In ${stateName}` : 'Across America'}, the public mostly ${publicVerb(verdict.side === 'against' ? words.againstVerb : words.forVerb, topicWord)}.`
                : verdict.kind === 'split'
                  ? `${placeWord} is split on ${topicWord}.`
                  : `Too few meetings where the public spoke to say which way ${placeWord} leans.`,
        )
        const line =
          counts && verdict && spoke > 0
            ? verdict.kind === 'majority'
              ? `${fmt(verdict.count)} of ${meetingsWord(verdict.of)} where the public spoke. `
              : `The public spoke in ${meetingsWord(spoke)}. `
            : ''
        return {
          headline: h,
          context: `${line}An AI read each meeting's transcript for the public's position: these are meetings, never counted speakers.`,
          right: counts ? (
            <>
              <TopicPositionsBreakdown counts={counts} words={words} scopeLabel={label} labelledBy="story-h-positions" />
              {/* Topics read with their own five positions (water fluoridation) also show them in full (#1274). */}
              <PositionBreakdown topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} fiveOnly />
            </>
          ) : null,
        }
      }
      case 'bills': {
        const L = legislation.data
        const all = L ? shadeStates(L.summary, { sinceYear: null, category: null }) : []
        const here = stateCode ? all.find((x) => x.state_code === stateCode) : undefined
        const enacted = L?.status_counts.enacted ?? 0
        const span = L ? yearSpan(L.summary) : null
        return {
          headline: loadingOr(legislation, 'state bills', () =>
            stateCode
              ? here
                ? `${stateName}'s legislature has taken up ${topicWord}: the furthest a bill got is ${STATUS_LABEL[here.status].toLowerCase()}.`
                : `${stateName}'s legislature has no bill on ${topicWord} in our record; ${fmt(all.length)} other states do.`
              : `${fmt(all.length)} statehouses have taken up ${topicWord}${span ? ` since ${span[0]}` : ''}.`,
          ),
          context: L
            ? `${fmt(L.total_bills)} state ${L.total_bills === 1 ? 'bill' : 'bills'} in our copy of OpenStates${enacted ? `, ${fmt(enacted)} enacted` : ''}. Each state is coloured by the furthest any of its bills got; choose one to see its bills.`
            : 'State bills in our copy of OpenStates.',
          right: <LegislationMap topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} />,
        }
      }
      case 'actions': {
        const A = localActions.data
        const w = actionLabels(def.slug)
        return {
          headline: loadingOr(localActions, 'votes', () =>
            A
              ? `${stateName ? `In ${stateName}` : 'Across America'}, local bodies ${w.advanced.charAt(0).toLowerCase()}${w.advanced.slice(1)} in ${meetingsWord(A.totals.advanced)} and ${w.blocked.charAt(0).toLowerCase()}${w.blocked.slice(1)} in ${fmt(A.totals.blocked)}.`
              : '',
          ),
          context: A
            ? `${meetingsWord(A.total)} where a council or board acted on it, ${fmt(A.totals.tabled_or_deferred)} of them put off, as an AI read the transcript.`
            : 'Meetings where a council or board acted on it, as an AI read the transcript.',
          right: <LocalActionsTracker topic={def.slug} stateCode={stateCode ?? undefined} scopeLabel={label} subject={subject} />,
        }
      }
      case 'companies':
        return {
          headline: loadingOr(
            companies,
            'companies',
            () => `The platforms named in ${stateName ? `${stateName}'s` : 'these'} meetings and decisions.`,
          ),
          context: companies.data ? `${fmt(named.length)} ${named.length === 1 ? 'company' : 'companies'} named in the record, counted from it.` : 'Counted from the record.',
          right: companies.data ? (
            <ul className="topic-story-list">
              {named.map((c) => {
                const brands = c.aliases.filter((a) => a !== c.company_name && !a.includes(','))
                return (
                  <li key={c.master_org_id} className="topic-story-item">
                    <p className="topic-story-item-title">
                      <Link to={`/organizations/${encodeURIComponent(c.master_org_id)}`}>{c.company_name}</Link>
                    </p>
                    {brands.length > 0 && <p className="topic-story-item-meta">{brands.join(', ')}</p>}
                      <p className="topic-story-item-body">
                        <Link to={`/search?q=${encodeURIComponent(companySearchTerm(c.company_name, c.newest?.evidence))}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`}>
                          {meetingsWord(c.meetings)}
                        </Link>
                        {' · '}
                        {fmt(c.decisions)} {c.decisions === 1 ? 'decision' : 'decisions'}
                      </p>
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
      case 'said': {
        const firstPage = meetings.data?.pages[0]
        const summary = saidSummary(def.slug, total, firstPage?.position_counts)
        const firstPassing = items.findIndex((m) => m.in_passing)
        return {
          headline: loadingOr(meetings, 'meetings', () => `What was said about ${topicWord} ${stateName ? `in ${stateName}` : 'across America'}.`),
          context: `${total ? `${meetingsWord(total)}, those where the public took a position or a speaker is named first. ` : ''}Passages are quoted from the transcript; a position is the meeting's, as an AI read it, never the speaker's.`,
          right: (
            <>
              {summary && (
                <p className="topic-story-summary" data-testid="said-summary">
                  {summary}
                </p>
              )}
              <ul className="topic-story-list">
                {(firstPassing < 0 ? items : items.slice(0, firstPassing)).map((m) => (
                  <SaidQuoteCard key={m.video_id} m={m} slug={def.slug} />
                ))}
              </ul>
              {firstPassing >= 0 && (
                <>
                  <h3 className="topic-story-subhead" data-testid="said-in-passing">
                    Mentioned in passing
                    {firstPage?.position_counts ? ` · ${meetingsWord(firstPage.position_counts.in_passing)}` : ''}
                  </h3>
                  <p className="stance-note">No public position, vote or named speaker on record for these meetings.</p>
                  <ul className="topic-story-list">
                    {items.slice(firstPassing).map((m) => (
                      <SaidQuoteCard key={m.video_id} m={m} slug={def.slug} />
                    ))}
                  </ul>
                </>
              )}
              {meetings.hasNextPage && (
                <button type="button" className="folio-btn" onClick={() => meetings.fetchNextPage()} disabled={meetings.isFetchingNextPage}>
                  {meetings.isFetchingNextPage ? 'Loading…' : 'Show more meetings'}
                </button>
              )}
            </>
          ),
        }
      }
      case 'decided': {
        const d = decisions.data
        return {
          headline: loadingOr(decisions, 'decisions', () => `What was decided on ${topicWord} ${stateName ? `in ${stateName}` : 'across America'}.`),
          context: d
            ? `${decisionsSummary(d.on_topic_total, d.in_passing_total, topicWord, 'it')} A decision counts as on ${topicWord} only when its wording names the policy, or the meeting's reading backs it; anything unsure is in passing.`
            : 'Decisions whose record mentions the topic, newest first.',
          right: d ? (
            <>
              <DecisionPanel
                heading={`Decisions on ${topicWord}`}
                total={d.on_topic_total}
                items={d.on_topic}
                testId="decisions-on-topic"
                lead={`${fmt(d.on_topic_total)} ${d.on_topic_total === 1 ? 'decision names' : 'decisions name'} the policy ${where}.`}
              />
              <DecisionPanel
                heading={`Mentioned in passing · ${fmt(d.in_passing_total)}`}
                total={d.in_passing_total}
                items={d.in_passing}
                testId="decisions-in-passing"
                lead={`${fmt(d.in_passing_total)} ${d.in_passing_total === 1 ? 'decision only mentions' : 'decisions only mention'} it in passing ${where}.`}
              />
              {d.total > d.on_topic.length + d.in_passing.length && (
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
      {/* The story's bar, shared with the Data Center Story (#1234, owner 2026-11-27): the title sentence (its place blank is
          the only place control), the screen's word, Close (×) at the top right and, on a wide screen, the segments. */}
      <ScopeBar
        backTo={homeHref}
        backLabel="Close"
        note={
          placeScope.resolved.reason ? (
            // Why the story shows a wider place than the one asked (#1285); the URL keeps the reader's choice.
            <p className="story-scope-note" role="note" data-scope-level={placeScope.resolved.level}>
              {placeScope.resolved.reason}
            </p>
          ) : undefined
        }
        close={<StoryClose to={homeHref} escape={!placeOpen} />}
        title={def.title}
        label={label}
        heading={
          <SentenceHeading
            template={titleTemplate}
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
                // Every live story, the same list as the Data Center Story's (#1224); choosing one opens it on its Overview,
                // keeping the place.
                options: storyTopicOptions(live, def.slug, topicWord),
                onChange: (v) => navigate(storyStartHref(v, scopeQ)),
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
      <p className="folio-sr-only" aria-live="polite">
        {screens[active] ? `${screens[active]!.eyebrow}, ${active + 1} of ${n}.` : ''}
      </p>
      <div className="stance-body">
        {/* Keyed by which screens are in the story: the pinned layout moves screens into its own wrappers (see DataStory). */}
        <div className="stance-acts" key={keepKey}>
          {screens.map((s, i) => {
            const v = screen(s.id)
            return (
              <StoryScreenFrame
                key={s.id}
                id={s.id}
                index={i}
                active={active === i}
                eyebrow={s.eyebrow}
                headline={v.headline}
                context={v.context}
                // The one Next is fixed at the bottom right (StoryNextButton); each screen keeps only its Back inline.
                nextLabel={null}
                onNext={() => goTo(i + 1)}
                onPrev={i > 0 ? () => goTo(i - 1) : undefined}
                right={v.right}
              >
                {v.lead}
              </StoryScreenFrame>
            )
          })}
        </div>
      </div>
      {/* The one way forward (#1234, owner 2026-11-27): a green Next fixed at the bottom right on every screen. Cover: starts
          the story; a screen: the next screen; the last screen: a quiet Done that closes the story. */}
      {active < n - 1 ? (
        <StoryNextButton label="Next" ariaLabel={`Next: ${screens[active + 1]?.eyebrow ?? ''}`.replace(/: $/, '')} onClick={() => goTo(Math.min(activeRef.current + 1, n - 1))} />
      ) : (
        <StoryNextButton label="Done" ariaLabel="Done: close the story" href={homeHref} quiet />
      )}
      {/* Phones: the bottom bar keeps Back and the progress dots; Next is the fixed button above, at its right end. */}
      {!wide && (
        <StoryBottomBar
          active={active}
          count={n}
          nextLabel={null}
          onNext={() => goTo(Math.min(activeRef.current + 1, n - 1))}
          withNext={false}
          prevLabel={active > 0 ? (screens[active - 1]?.eyebrow ?? null) : null}
          onPrev={() => goTo(Math.max(activeRef.current - 1, 0))}
          storyHref={homeHref}
          storyLabel="Done"
          storyIsNext={false}
        />
      )}
      <p className="stance-keys">Keys: → or PageDown next · ← or PageUp back · Home and End jump to the ends · on a phone, swipe left or right</p>
    </div>
  )
}
