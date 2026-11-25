import { Link } from 'react-router-dom'
import { Briefcase, Building2, ChevronRight, Droplet, Landmark, Megaphone, type LucideIcon } from 'lucide-react'

interface Topic {
  /** The story screen it opens. */
  screen: string
  title: string
  blurb: string
  Icon: LucideIcon
  tint: string
  ink: string
}

// The story's own screens, as topics to browse (#995). Words only: every count lives on the screen it links to.
const TOPICS: Topic[] = [
  { screen: 'voices', title: 'Public opposition', blurb: 'Who spoke for and against, in their own words.', Icon: Megaphone, tint: '#dcfce7', ink: '#15803d' },
  { screen: 'projects', title: 'Data center projects', blurb: 'Proposed projects and where they stand.', Icon: Building2, tint: '#dbeafe', ink: '#1d4ed8' },
  { screen: 'decisions', title: 'Local government responses', blurb: 'What councils and boards decided.', Icon: Landmark, tint: '#ede9fe', ink: '#6d28d9' },
  { screen: 'concerns', title: 'Environment and resources', blurb: 'Water, power and land, as residents raised them.', Icon: Droplet, tint: '#ffedd5', ink: '#c2410c' },
  { screen: 'jobs', title: 'Jobs and promises', blurb: 'The jobs claimed in meetings, construction and operations.', Icon: Briefcase, tint: '#ccfbf1', ink: '#0f766e' },
]

/** "Browse topics" under the home story (#995): each card opens that screen of the Data Center Story for the page's place. */
export default function HomeTopicStrip({ query }: { query: string }) {
  const sep = query ? '&' : '?'
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
        {TOPICS.map(({ screen, title, blurb, Icon, tint, ink }) => (
          <li key={screen}>
            <Link to={`/stories/data-centers${query}${sep}screen=${screen}`} className="home-topic">
              <span className="home-topic-icon" style={{ background: tint, color: ink }} aria-hidden="true">
                <Icon size={26} strokeWidth={1.8} />
              </span>
              <span className="home-topic-text">
                <span className="home-topic-title">{title}</span>
                <span className="home-topic-blurb">{blurb}</span>
                <span className="home-topic-go">
                  Explore topic <span aria-hidden="true">→</span>
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
