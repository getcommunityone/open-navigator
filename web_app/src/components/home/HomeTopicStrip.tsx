import { Link } from 'react-router-dom'
import { Bike, Camera, ChevronRight, House, ScanLine, Server, type LucideIcon } from 'lucide-react'

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
}

// Browse topics (#1013, #1025), in the owner's order: Data centers (the default story above), Short-term rentals, then
// the stories still to come. A live card selects the story shown above it; the rest say "Coming soon" and do nothing.
const TOPICS: Topic[] = [
  { key: 'dc', title: 'Data centers', blurb: 'Who spoke up, the sites and projects, and what was decided.', Icon: Server, tint: '#ccfbf1', ink: '#0f766e', story: 'data-centers' },
  { key: 'str', title: 'Short-term rentals', blurb: 'Airbnb, VRBO and vacation rentals, in the words said at meetings.', Icon: House, tint: '#dcfce7', ink: '#15803d', story: 'short-term-rentals' },
  { key: 'flock', title: 'Flock', blurb: 'Flock Safety cameras and the contracts behind them.', Icon: Camera, tint: '#dbeafe', ink: '#1d4ed8' },
  { key: 'lpr', title: 'License plate readers', blurb: 'Automated plate readers: who uses them and for what.', Icon: ScanLine, tint: '#ede9fe', ink: '#6d28d9' },
  { key: 'bike', title: 'Bike lanes', blurb: 'Bike lanes and paths, as councils weigh them.', Icon: Bike, tint: '#ffedd5', ink: '#c2410c' },
]

interface Props {
  /** The page's place (?state=&city=), carried by the "all stories" link. */
  query: string
  /** The story shown above the strip. */
  selected: HomeStoryKey
  onSelect: (story: HomeStoryKey) => void
}

/** "Browse topics" under the home story: picks which story the card above shows (Data centers by default). */
export default function HomeTopicStrip({ query, selected, onSelect }: Props) {
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
        {TOPICS.map(({ key, title, blurb, Icon, tint, ink, story }) => {
          const on = story != null && story === selected
          const body = (
            <>
              <span className="home-topic-icon" style={{ background: tint, color: ink, opacity: story ? 1 : 0.55 }} aria-hidden="true">
                <Icon size={26} strokeWidth={1.8} />
              </span>
              <span className="home-topic-text">
                <span className="home-topic-title">{title}</span>
                <span className="home-topic-blurb">{blurb}</span>
                {!story ? (
                  <span className="home-topic-soon">Coming soon</span>
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
                <button type="button" className={'home-topic' + (on ? ' is-on' : '')} aria-pressed={on} onClick={() => onSelect(story)}>
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
    </nav>
  )
}
