import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bike, Camera, ChevronRight, Crosshair, HandHeart, House, ScanLine, Server, ShieldCheck, Volleyball, type LucideIcon } from 'lucide-react'
import TopicCompaniesPanel from './TopicCompaniesPanel'

/** The live home stories the strip can select (#1025). */
export type HomeStoryKey = 'data-centers' | 'short-term-rentals'

interface Topic {
  key: string
  title: string
  blurb: string
  Icon: LucideIcon
  tint: string
  ink: string
  /** The home story it selects; absent while the story is coming soon. */
  story?: HomeStoryKey
  /** The curated topic whose companies it shows (#1052); absent when none are tracked. */
  topic?: string
}

// Browse topics (#1013, #1025), in the owner's order: Data centers (the default story above), Short-term rentals, then
// the stories still to come. A live card selects the story shown above it; the rest say "Coming soon" and do nothing.
const TOPICS: Topic[] = [
  { key: 'dc', title: 'Data centers', blurb: 'Who spoke up, the sites and projects, and what was decided.', Icon: Server, tint: '#ccfbf1', ink: '#0f766e', story: 'data-centers', topic: 'data-centers' },
  { key: 'str', title: 'Short-term rentals', blurb: 'Airbnb, VRBO and vacation rentals, in the words said at meetings.', Icon: House, tint: '#dcfce7', ink: '#15803d', story: 'short-term-rentals', topic: 'short-term-rentals' },
  { key: 'flock', title: 'Flock', blurb: 'Flock Safety cameras and the contracts behind them.', Icon: Camera, tint: '#dbeafe', ink: '#1d4ed8', topic: 'license-plate-readers' },
  { key: 'guns', title: 'Guns', blurb: 'Firearm rules, gun shows and ranges, and gunshot detection, as councils weigh them.', Icon: Crosshair, tint: '#fee2e2', ink: '#b91c1c', topic: 'guns' },
  { key: 'lpr', title: 'License plate readers', blurb: 'Automated plate readers: who uses them and for what.', Icon: ScanLine, tint: '#ede9fe', ink: '#6d28d9', topic: 'license-plate-readers' },
  { key: 'pickleball', title: 'Pickleball', blurb: 'Courts, noise and new venues, as councils and parks boards weigh them.', Icon: Volleyball, tint: '#ecfccb', ink: '#4d7c0f', topic: 'pickleball' },
  { key: 'bike', title: 'Bike lanes', blurb: 'Bike lanes and paths, as councils weigh them.', Icon: Bike, tint: '#ffedd5', ink: '#c2410c' },
  // Guides, not meeting stories (#1078, #1079): coming soon, with no companies or counts until real data backs them.
  { key: 'nonprofit', title: 'Starting a nonprofit', blurb: 'Every step, filing and fee to start one, state by state.', Icon: HandHeart, tint: '#fce7f3', ink: '#be185d' },
  { key: 'insurance', title: 'Insurance shopping', blurb: 'Are you paying too much? What regulators publish, made simple.', Icon: ShieldCheck, tint: '#e0f2fe', ink: '#0369a1' },
]

interface Props {
  /** The page's place (?state=&city=), carried by the "all stories" link. */
  query: string
  /** The story shown above the strip. */
  selected: HomeStoryKey
  onSelect: (story: HomeStoryKey) => void
  /** The page's scope, for the companies panel (CLAUDE.md scope-label rule). */
  stateCode?: string
  city?: string | null
  scopeLabel: string
}

/** "Browse topics" under the home story: picks which story the card above shows (Data centers by default). */
export default function HomeTopicStrip({ query, selected, onSelect, stateCode, city = null, scopeLabel }: Props) {
  // The card whose companies are shown (#1052): the live story's card, or a coming-soon card the reader picked.
  const storyCard = TOPICS.find((t) => t.story === selected)?.key ?? TOPICS[0]!.key
  const [picked, setPicked] = useState<string>(storyCard)
  useEffect(() => setPicked(storyCard), [storyCard])
  const shown = TOPICS.find((t) => t.key === picked && t.topic)
  return (
    <nav aria-labelledby="home-topics-h" className="home-topics">
      <div className="home-topics-head">
        <p id="home-topics-h" className="font-mono-x">
          Browse topics
        </p>
        <Link to={`/stories${query}`} aria-label="All data stories" className="home-topics-all">
          <ChevronRight size={18} aria-hidden="true" />
        </Link>
      </div>
      <ul className="home-topics-list">
        {TOPICS.map(({ key, title, blurb, Icon, tint, ink, story, topic }) => {
          const on = story != null && story === selected
          const companiesOn = !story && key === picked
          const body = (
            <>
              <span className="home-topic-icon" style={{ background: tint, color: ink, opacity: story ? 1 : 0.55 }} aria-hidden="true">
                <Icon size={26} strokeWidth={1.8} />
              </span>
              <span className="home-topic-text">
                <span className="home-topic-title">{title}</span>
                <span className="home-topic-blurb">{blurb}</span>
                {!story ? (
                  <span className="home-topic-soon">
                    Coming soon{topic ? (companiesOn ? ' · Companies below' : ' · See companies') : ''}
                  </span>
                ) : on ? (
                  <span className="home-topic-on">Showing above</span>
                ) : (
                  <span className="home-topic-go">
                    Show this story <span aria-hidden="true">→</span>
                  </span>
                )}
              </span>
            </>
          )
          return (
            <li key={key}>
              {story ? (
                <button type="button" className={'home-topic' + (on ? ' is-on' : '')} aria-pressed={on} onClick={() => { onSelect(story); setPicked(key) }}>
                  {body}
                </button>
              ) : topic ? (
                // Coming soon, but its companies are tracked: picking it shows them below (the story above stays).
                <button type="button" className={'home-topic is-soon' + (companiesOn ? ' is-picked' : '')} aria-pressed={companiesOn} onClick={() => setPicked(key)}>
                  {body}
                </button>
              ) : (
                <div className="home-topic is-soon" aria-disabled="true">
                  {body}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {shown?.topic && (
        <TopicCompaniesPanel queryId={shown.topic} title={shown.title} stateCode={stateCode} city={city} scopeLabel={scopeLabel} />
      )}
    </nav>
  )
}
