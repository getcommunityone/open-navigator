import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { CAPTION_COPY, captionText, pickCaption } from '../../utils/storyCaption'
import HomeTopicStrip, { type HomeStoryKey } from './HomeTopicStrip'
import HomeTopicStoryCard from './HomeTopicStoryCard'
import { useTopicStories } from '../../hooks/useTopicStories'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'
import { Ban, Landmark, Quote, type LucideIcon } from 'lucide-react'
import { heroPoints, type HeroPointIcon } from '../../utils/heroPoints'
import { nextStoryLink } from '../../utils/storyNav'
import { scopedMeetingHref } from '../stance/quoteCardUtils'

const POINT_ICONS: Record<HeroPointIcon, LucideIcon> = { quote: Quote, stop: Ban, scale: Landmark }

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
 * - the story's title from the caption picker (#1125), the same template the story header uses, for the page's scope,
 *   with its basis line and Start;
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
  // The title (#1125): the caption picker over the caption facts for this scope, shared with the story header.
  const dcFacts = useQuery({
    queryKey: ['caption-facts', 'data-centers', stateCode ?? '', scope.city ?? ''],
    queryFn: () => fetchTopicCaptionFacts('data-centers', stateCode, scope.city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const pending = dcFacts.isPending
  const dcCaption = pickCaption('data-centers', dcFacts.data, scope)
  // Which story the card shows (#1025): Data centers by default; Browse topics switches it, carried as ?story= so a
  // refresh, a deep link or Back keeps it (CLAUDE.md, scope via the URL).
  const [sp, setSp] = useSearchParams()
  // Any live topic story can be shown (#1133); an unknown or not-yet-loaded ?story= shows data centers.
  const topicStories = useTopicStories()
  const asked = sp.get('story') ?? ''
  const topicDef = asked ? topicStories.stories[asked] : undefined
  const story: HomeStoryKey = topicDef ? asked : 'data-centers'
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
    return out
  }, [national.data, speakers.data, stateCode, scope.city])
  // The three numbered points (#1122): national figures from the record, a point without data left out.
  const points = useMemo(
    () => (speakers.data?.available ? heroPoints(speakers.data.lean_totals, speakers.data.totals) : []),
    [speakers.data],
  )
  const nextDc = nextStoryLink('data-centers', q, topicStories.live)

  return (
    <section id="data-stories" aria-labelledby="home-story-dc" className="home-stories" style={{ scrollMarginTop: 72 }}>
      <div className="home-stories-inner">
        {topicDef ? (
          <HomeTopicStoryCard def={topicDef} scope={scope} query={q} label={label} />
        ) : (
        <div className="home-story-card">
          <div className="home-story-text">
            <p className="font-mono-x home-story-eyebrow">Data story · {STORY.title}</p>
            {/* While the record loads, the headline's place is held (invisible) so the question doesn't flash first. */}
            <h1 id="home-story-dc" className="font-display home-story-headline" aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
              {dcCaption.kind === 'question' ? STORY.question : captionText(dcCaption, CAPTION_COPY['data-centers']!.topic)}
            </h1>
            {/* The subhead speaks for the country, so it shows only with the national "hates" title. */}
            {dcCaption.kind === 'sentiment' && !stateCode && STORY.conclusion && <p className="home-story-subhead">{STORY.conclusion.subhead}</p>}
            {dcCaption.basis && (
              <p className="home-story-basis">
                {dcCaption.basis}
              </p>
            )}
            {points.length > 0 && (
              <ol className="home-story-points" aria-label="What the record shows, nationally">
                {points.map((p) => {
                  const Icon = POINT_ICONS[p.icon]
                  return (
                    <li key={p.icon} className="home-story-point">
                      <span className="home-story-point-icon" aria-hidden="true">
                        <Icon size={20} strokeWidth={2.2} />
                      </span>
                      <div>
                        <p className="home-story-point-n font-mono-x">{p.n}</p>
                        <p className="home-story-point-title">“{p.title}”</p>
                        <p className="home-story-point-line">{p.line}</p>
                      </div>
                    </li>
                  )
                })}
              </ol>
            )}
            <div className="home-story-actions">
              <Link to={`/stories/data-centers${q}`} className="home-story-start">
                Start the story{label === 'National' ? '' : ` for ${label}`} <span aria-hidden="true">→</span>
              </Link>
              <Link to={nextDc.href} className="home-story-next">
                {nextDc.label} <span aria-hidden="true">→</span>
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
