import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { useStoryConclusionState } from '../stance/useStoryConclusion'
import HomeTopicStrip from './HomeTopicStrip'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'

interface Props {
  /** The home page's place, so the Start button and the topic links carry it (CLAUDE.md, scope label rule). */
  stateCode?: string
  city?: string | null
}

const STORY = STORIES['data-centers']!

/**
 * Home `#data-stories`, the top of the home page (#975, #985, #989, #995):
 * - the story's conclusion headline (gated on the national record; else its question), subtitle, basis and Start;
 * - a US map with a pin per state that discussed data centers, each linking to that state's story, and a card quoting the
 *   state's newest meeting passage, verbatim, with where and when it was said;
 * - Browse topics: the story's screens, for the page's place.
 */
export default function HomeDataStories({ stateCode, city = null }: Props) {
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scope = { stateCode, stateName, city: stateCode ? city : null }
  const label = storyScopeLabel(scope)
  const q = scopeQuery(scope)
  const { conclusion, pending } = useStoryConclusionState('data-centers')

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
    const out = new Map<string, StateQuote>()
    const sides = speakers.data?.quotes
    for (const side of ['against', 'for', 'question'] as const) {
      for (const sq of sides?.[side] ?? []) {
        if (!sq.state_code || out.has(sq.state_code) || !sq.quote) continue
        out.set(sq.state_code, {
          place: [sq.jurisdiction_name, sq.state_code].filter(Boolean).join(', '),
          side,
          who: sq.speaker_role ?? null,
          text: sq.quote,
          date: sq.meeting_date ?? null,
          meeting: sq.decision_headline ?? null,
          url: sq.jump_url ?? sq.video_url ?? null,
        })
      }
    }
    for (const m of national.data?.items ?? []) {
      if (!m.state_code || out.has(m.state_code) || !m.evidence) continue
      out.set(m.state_code, {
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
                highlight={stateCode ?? null}
                href={(code) => `/stories/data-centers?state=${encodeURIComponent(code)}`}
              />
            )}
          </div>
        </div>

        <HomeTopicStrip query={q} />
      </div>
    </section>
  )
}
