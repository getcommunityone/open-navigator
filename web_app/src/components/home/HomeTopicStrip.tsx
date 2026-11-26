import { Link } from 'react-router-dom'
import { Bike, Camera, ChevronRight, House, ScanLine, type LucideIcon } from 'lucide-react'

interface Topic {
  key: string
  title: string
  blurb: string
  Icon: LucideIcon
  tint: string
  ink: string
  /** The story it opens; absent while the story is coming soon. */
  to?: string
}

// Browse topics (#1013): the other data stories, in the owner's order. Only stories that exist link; the rest say
// "Coming soon" and are not links. Words only: every count lives in the story it opens.
const TOPICS: Topic[] = [
  { key: 'str', title: 'Short-term rentals', blurb: 'Airbnb, VRBO and vacation rentals, in the words said at meetings.', Icon: House, tint: '#dcfce7', ink: '#15803d', to: '/stories/short-term-rentals' },
  { key: 'flock', title: 'Flock', blurb: 'Flock Safety cameras and the contracts behind them.', Icon: Camera, tint: '#dbeafe', ink: '#1d4ed8' },
  { key: 'lpr', title: 'License plate readers', blurb: 'Automated plate readers: who uses them and for what.', Icon: ScanLine, tint: '#ede9fe', ink: '#6d28d9' },
  { key: 'bike', title: 'Bike lanes', blurb: 'Bike lanes and paths, as councils weigh them.', Icon: Bike, tint: '#ffedd5', ink: '#c2410c' },
]

/** "Browse topics" under the home story: each live card opens its story for the page's place (scope carried). */
export default function HomeTopicStrip({ query }: { query: string }) {
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
        {TOPICS.map(({ key, title, blurb, Icon, tint, ink, to }) => {
          const body = (
            <>
              <span className="home-topic-icon" style={{ background: tint, color: ink, opacity: to ? 1 : 0.55 }} aria-hidden="true">
                <Icon size={26} strokeWidth={1.8} />
              </span>
              <span className="home-topic-text">
                <span className="home-topic-title">{title}</span>
                <span className="home-topic-blurb">{blurb}</span>
                {to ? (
                  <span className="home-topic-go">
                    Explore topic <span aria-hidden="true">→</span>
                  </span>
                ) : (
                  <span className="home-topic-soon">Coming soon</span>
                )}
              </span>
            </>
          )
          return (
            <li key={key}>
              {to ? (
                <Link to={`${to}${query}`} className="home-topic">
                  {body}
                </Link>
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
