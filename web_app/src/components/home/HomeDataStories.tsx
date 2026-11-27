import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { CAPTION_COPY, captionSubhead, captionText, isLongTitle, pickCaption, storyStartLabel } from '../../utils/storyCaption'
import '../../styles/story-actions.css'
import HomeTopicStrip, { type HomeStoryKey } from './HomeTopicStrip'
import HomeTopicStoryCard, { HomeStoryDrill } from './HomeTopicStoryCard'
import { useTopicStories } from '../../hooks/useTopicStories'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'
import { storyHeroPoints } from '../../utils/heroPoints'
import { HERO_POINT_GLYPHS } from './heroPointGlyphs'
import { nextStoryLink } from '../../utils/storyNav'
import { scopedMeetingHref } from '../stance/quoteCardUtils'


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
 * - the story's title from the caption picker (#1125), the same one the story header and Overview use, for the page's
 *   scope, with its scoped subhead (#1134), basis line, numbered points and Start;
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
  const dcSubhead = captionSubhead(dcCaption, 'data-centers', scope)
  const dcTitle = dcCaption.kind === 'question' ? STORY.question : captionText(dcCaption, CAPTION_COPY['data-centers']!.topic)
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
  // The place's own positions (scope_lean_totals, totals) for the points (#1134).
  const scopedPositions = useQuery({
    queryKey: ['home', 'hero', 'positions', stateCode, scope.city],
    queryFn: () => fetchDataCenterPositions({ state: stateCode, city: scope.city ?? undefined, limit: 1 }),
    enabled: Boolean(stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  // The three numbered points (#1122): the place's own figures where it has them, else national ones marked "Nationally:".
  const points = useMemo(
    // Held until the place's own figures settle, so a state scope never flashes "Nationally:" points first (#1134).
    () =>
      stateCode && scopedPositions.isPending
        ? []
        : storyHeroPoints(speakers.data, stateCode ? scopedPositions.data : null, stateCode ? label : null),
    [speakers.data, scopedPositions.data, scopedPositions.isPending, stateCode, label],
  )
  const nextDc = nextStoryLink('data-centers', q, topicStories.live)

  return (
    <section id="data-stories" aria-labelledby="home-story-dc" className="home-stories" style={{ scrollMarginTop: 72 }}>
      <div className="home-stories-inner">
        {topicDef ? (
          <HomeTopicStoryCard def={topicDef} scope={scope} query={q} label={label} next={nextStoryLink(topicDef.slug, q, topicStories.live)} />
        ) : (
        <div className="home-story-card">
          <div className="home-story-text">
            <p className="font-mono-x home-story-eyebrow">Data story · {STORY.title}</p>
            {/* While the record loads, the headline's place is held (invisible) so the question doesn't flash first. */}
            <h1 id="home-story-dc" className={`font-display home-story-headline${isLongTitle(dcTitle) ? ' is-long' : ''}`} aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
              {dcTitle}
            </h1>
            {/* The subhead speaks only for the caption's scope (#1134): never a national claim on a place's page. */}
            {!pending && dcSubhead && <p className="home-story-subhead">{dcSubhead}</p>}
            {dcCaption.basis && (
              <p className="home-story-basis">
                {dcCaption.basis}
              </p>
            )}
            {/* Next steps first (#1176): Start, Next story and the drill-down hint sit in the first screen. */}
            <div className="home-story-actions">
              <Link to={`/stories/data-centers${q}`} className="home-story-start">
                {storyStartLabel('data-centers', label)} <span aria-hidden="true">→</span>
              </Link>
              <Link to={nextDc.href} className="home-story-next">
                {nextDc.label} <span aria-hidden="true">→</span>
              </Link>
            </div>
            <HomeStoryDrill label={label} />
            {points.length > 0 && (
              <ol className="home-story-points" aria-label={stateCode ? `What the record shows for ${label}` : 'What the record shows, nationally'}>
                {points.map((p) => {
                  const Icon = HERO_POINT_GLYPHS[p.icon]
                  return (
                    <li key={p.icon} className="home-story-point">
                      <span className="home-story-point-icon" aria-hidden="true">
                        <Icon width={28} height={28} />
                      </span>
                      <div>
                        <p className="home-story-point-title">
                          <span className="home-story-point-n">{p.n}</span>“{p.title}”
                        </p>
                        <p className="home-story-point-line">{p.line}</p>
                      </div>
                    </li>
                  )
                })}
              </ol>
            )}
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
