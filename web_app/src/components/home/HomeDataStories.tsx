import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { useStoryConclusionState } from '../stance/useStoryConclusion'
import HomeTopicStrip, { type HomeStoryKey } from './HomeTopicStrip'
import { fetchTopicStates } from '../../api/topics'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'

interface Props {
  /** The home page's place, so the Start button and the topic links carry it (CLAUDE.md, scope label rule). */
  stateCode?: string
  city?: string | null
}

const STORY = STORIES['data-centers']!
/** A state's map passages, in order (speakers' own words first, then meeting passages, newest first), at most this many. */
const QUOTES_PER_STATE = 12

function pushQuote(out: Map<string, StateQuote[]>, code: string, q: StateQuote) {
  const list = out.get(code)
  if (!list) out.set(code, [q])
  else if (list.length < QUOTES_PER_STATE) list.push(q)
}

/**
 * Home `#data-stories`, the top of the home page (#975, #985, #989, #995):
 * - the story's conclusion headline (gated on the national record; else its question), subtitle, basis and Start;
 * - a US map of small boxes in each state's shape (#1087), split by the real counts of speakers for, against, asking a
 *   question or taking no side where any are on record, each state linking to its story, and a card quoting one of the
 *   state's real passages, verbatim, with where and when it was said;
 * - Browse topics: picks the story the card shows (Data centers by default, Short-term rentals; others coming soon), #1025.
 */
export default function HomeDataStories({ stateCode, city = null }: Props) {
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scope = { stateCode, stateName, city: stateCode ? city : null }
  const label = storyScopeLabel(scope)
  const q = scopeQuery(scope)
  const { conclusion, pending } = useStoryConclusionState('data-centers')
  // Which story the card shows (#1025): Data centers by default; Browse topics switches it, carried as ?story= so a
  // refresh, a deep link or Back keeps it (CLAUDE.md, scope via the URL).
  const [sp, setSp] = useSearchParams()
  const story: HomeStoryKey = sp.get('story') === 'short-term-rentals' ? 'short-term-rentals' : 'data-centers'
  const selectStory = (next: HomeStoryKey) =>
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev)
        if (next === 'data-centers') n.delete('story')
        else n.set('story', next)
        return n
      },
      { replace: true, preventScrollReset: true },
    )
  // Short-term rentals: meetings per state and each state's newest passage, from the transcript record (#1013).
  const str = useQuery({
    queryKey: ['topic-story', 100003, 'states'],
    queryFn: () => fetchTopicStates(100003),
    enabled: story === 'short-term-rentals',
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const strQuotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    for (const m of str.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      pushQuote(out, m.state_code, {
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        url: m.video_url ?? null,
      })
    }
    return out
  }, [str.data])
  const strScoped = useMemo(() => {
    const d = str.data
    if (!d) return null
    if (!stateCode) return { meetings: d.total_meetings, states: d.states.length }
    return { meetings: d.states.find((x) => x.state_code === stateCode)?.meetings ?? 0, states: 1 }
  }, [str.data, stateCode])

  // National: every state's own count, and the newest passages to quote (newest first, so the first per state is its newest).
  const national = useQuery({
    queryKey: ['home', 'story-map', 'meeting-mentions', 500],
    queryFn: () => fetchDataCenterMeetingMentions({ limit: 500 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  // Speakers' own words with their recorded side, preferred over a meeting passage where a state has them.
  const speakers = useQuery({
    // The API returns at most 10 quotes per side (POSITION_QUOTES_MAX).
    queryKey: ['home', 'story-map', 'positions', 10],
    queryFn: () => fetchDataCenterPositions({ limit: 10 }),
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
          who: [sq.speaker_display_name, sq.speaker_role].filter(Boolean).join(' · ') || null,
          text: sq.quote,
          date: sq.meeting_date ?? null,
          meeting: sq.decision_headline ?? null,
          url: sq.jump_url ?? sq.video_url ?? null,
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
        url: m.jump_url ?? m.video_url ?? null,
      })
    }
    return out
  }, [national.data, speakers.data])

  return (
    <section id="data-stories" aria-labelledby="home-story-dc" className="home-stories" style={{ scrollMarginTop: 72 }}>
      <div className="home-stories-inner">
        {story === 'short-term-rentals' ? (
        <div className="home-story-card">
          <div className="home-story-text">
            <p className="font-mono-x home-story-eyebrow">Data story · Short-term rentals</p>
            <h1 id="home-story-dc" className="font-display home-story-headline" aria-busy={str.isPending || undefined} style={str.isPending ? { visibility: 'hidden' } : undefined}>
              {strScoped == null
                ? 'Short-term rentals'
                : stateName
                  ? `Short-term rentals came up in ${strScoped.meetings.toLocaleString('en-US')} ${strScoped.meetings === 1 ? 'meeting' : 'meetings'} in ${stateName}.`
                  : `Short-term rentals came up in ${strScoped.meetings.toLocaleString('en-US')} meetings across ${strScoped.states} states.`}
            </h1>
            <p className="home-story-subhead">Airbnb, VRBO and vacation rentals: where local governments are talking about them, in the words said at the meeting.</p>
            <p className="home-story-basis">Counted from local meeting recordings and transcripts that mention the topic.</p>
            <div style={{ marginTop: 18 }}>
              <Link to={`/stories/short-term-rentals${stateCode ? `?state=${encodeURIComponent(stateCode)}` : ''}`} className="home-story-start">
                Start the story{stateName ? ` for ${stateName}` : ''} <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
          <div className="home-story-map">
            {str.isError ? (
              <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
            ) : (
              <StoryStatesMap
                byState={str.data?.states}
                quotes={strQuotes}
                highlight={stateCode ?? null}
                href={(code) => `/stories/short-term-rentals?state=${encodeURIComponent(code)}`}
                subject="short-term rentals"
              />
            )}
          </div>
        </div>
        ) : (
        <div className="home-story-card">
          <div className="home-story-text">
            <p className="font-mono-x home-story-eyebrow">Data story · {STORY.title}</p>
            {/* While the record loads, the headline's place is held (invisible) so the question doesn't flash first. */}
            <h1 id="home-story-dc" className="font-display home-story-headline" aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
              {conclusion ? conclusion.headline : STORY.question}
            </h1>
            {conclusion && (
              <>
                <p className="home-story-subhead">{conclusion.subhead}</p>
                <p className="home-story-basis">{conclusion.basis}</p>
              </>
            )}
            <div style={{ marginTop: 18 }}>
              <Link to={`/stories/data-centers${q}`} className="home-story-start">
                Start the story{label === 'National' ? '' : ` for ${label}`} <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>

          <div className="home-story-map">
            {national.isError ? (
              <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
            ) : (
              <StoryStatesMap
                byState={national.data?.counts?.by_state}
                quotes={quotes}
                stance={speakers.data?.available ? (speakers.data.by_state ?? []) : undefined}
                highlight={stateCode ?? null}
                href={(code) => `/stories/data-centers?state=${encodeURIComponent(code)}`}
              />
            )}
          </div>
        </div>
        )}

        <HomeTopicStrip query={q} selected={story} onSelect={selectStory} stateCode={stateCode} city={scope.city} scopeLabel={label} />
      </div>
    </section>
  )
}
