import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { useTopicUpcoming } from '../../hooks/useTopicUpcoming'
import { useTopicOutcomes } from '../../hooks/useTopicOutcomes'
import { stepScreen } from '../../utils/topicOutcomes'
import { upcomingCardLine } from '../../utils/topicUpcoming'
import { outcomeCardHref, type OutcomeCard } from '../../utils/homeOutcomes'
import { useBoxFlight } from '../stance/BoxFlightProvider'
import './HomeOutcomesScroller.css'

interface Props {
  /** The story the home card shows (?story=, data centers by default). */
  topic: string
  /** The topic in words ("data centers"). */
  subject: string
  stateCode: string | null
  /** Only for a story drawn at city grain (the Data Center Story); topic stories are by state. */
  city: string | null
  /** The scope label in effect, the same words as the story card above. */
  label: string
  /** Whether the story is the Data Center Story (its screens differ from a topic story's). */
  dataCenterStory: boolean
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The home page's strip from the story to what happens next (#1302): Coming up first (where a reader can still act), then
 * meetings on record, what local bodies did (#1314) and the state bills still open. Each card is one real number and one line, and opens that screen of
 * the story at the same place (?state=&city= read from the home page, never changed here). Below the hero map, above
 * Browse topics; a sideways scroll on a phone.
 */
export default function HomeOutcomesScroller({ topic, subject, stateCode, city, label, dataCenterStory }: Props) {
  const boxFlight = useBoxFlight()
  const upcoming = useTopicUpcoming(topic, stateCode, city)
  const facts = useQuery({
    queryKey: ['caption-facts', topic, stateCode ?? '', city ?? ''],
    queryFn: () => fetchTopicCaptionFacts(topic, stateCode ?? undefined, city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  // What local bodies did (#1314), from the chain's counts.
  const outcomes = useTopicOutcomes(topic, stateCode, city)
  const acted = outcomes.data?.steps.actions
  const u = upcoming.data
  const meetings = facts.data?.meetings ?? null
  const bills = u?.pending_bills.total ?? null
  const scope = { stateCode, city: dataCenterStory ? city : null }

  const cards: OutcomeCard[] = [
    {
      key: 'upcoming',
      eyebrow: 'Coming up',
      value: upcoming.isPending ? null : upcoming.isError ? null : (u?.total ?? 0),
      line: upcoming.isPending ? 'Loading…' : upcoming.isError ? 'Could not be loaded right now.' : upcomingCardLine(u, label),
      screen: 'upcoming',
      lead: true,
    },
    {
      key: 'meetings',
      eyebrow: 'Meetings',
      value: facts.isPending || facts.isError ? null : (meetings ?? 0),
      line: facts.isPending
        ? 'Loading…'
        : facts.isError
          ? 'Could not be loaded right now.'
          : (meetings ?? 0) === 0
            ? `No recorded meetings on ${subject} yet.`
            : `${meetings === 1 ? 'Meeting' : 'Meetings'} where ${subject} came up.`,
      screen: dataCenterStory ? 'meetings' : 'timeline',
    },
    {
      key: 'votes',
      eyebrow: 'Votes',
      value: outcomes.isPending || outcomes.isError || !acted?.available ? null : acted.count,
      line: outcomes.isPending
        ? 'Loading…'
        : outcomes.isError || !acted?.available
          ? 'Could not be loaded right now.'
          : acted.count === 0
            ? 'No recorded votes or delays yet.'
            : `Meetings where a council or board acted on ${subject}.`,
      screen: dataCenterStory ? 'outcomes' : (stepScreen('actions', false) ?? 'outcomes'),
    },
    {
      key: 'bills',
      eyebrow: 'State bills',
      value: upcoming.isPending || upcoming.isError ? null : (bills ?? 0),
      line: upcoming.isPending
        ? 'Loading…'
        : upcoming.isError
          ? 'Could not be loaded right now.'
          : (bills ?? 0) === 0
            ? `No open state bill${stateCode ? ` in ${u?.state ?? stateCode}` : ''} yet.`
            : `Still open in the legislature${stateCode ? ` (${u?.state ?? stateCode})` : ''}.`,
      // The Data Center Story lists open bills on its Coming up screen; topic stories have a State bills map.
      screen: dataCenterStory ? 'upcoming' : 'bills',
    },
  ]

  return (
    <section className="home-outcomes" aria-labelledby="home-outcomes-h">
      <p id="home-outcomes-h" className="home-outcomes-h">
        What happens next · <span className="home-outcomes-scope">{label}</span>
      </p>
      <ol className="home-outcomes-list">
        {cards.map((c) => (
          <li key={c.key}>
            <Link
              to={outcomeCardHref(topic, scope, c.screen)}
              className={`home-outcome${c.lead ? ' is-lead' : ''}`}
              onClick={(e) => {
                const src = document.querySelector<HTMLElement>('.home-story-map') ?? e.currentTarget
                boxFlight.launch({
                  source: src,
                  focusGroup: c.key,
                  targetSelector: '.stance-story [data-live], .stance-story [data-panel]',
                })
              }}
            >
              <span className="home-outcome-eyebrow">{c.eyebrow}</span>
              <span className="home-outcome-num" aria-busy={c.value == null || undefined}>
                {c.value == null ? '—' : fmt(c.value)}
              </span>
              <span className="home-outcome-line">{c.line}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}
