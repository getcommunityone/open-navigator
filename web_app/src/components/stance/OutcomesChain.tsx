import { Link } from 'react-router-dom'
import { useTopicOutcomes } from '../../hooks/useTopicOutcomes'
import { highlightSnippet } from '../../lib/highlight'
import { chainSteps, stepScreen, type ChainStepId } from '../../utils/topicOutcomes'
import { upcomingDate } from '../../utils/topicUpcoming'
import type { OutcomeExample } from '../../api/topicOutcomes'
import './storyCharts.css'
import './OutcomesChain.css'

interface Props {
  topic: string
  stateCode?: string | null
  city?: string | null
  scopeLabel: string
  subject: string
  /** The topic's own words for the two kinds of action ("Voted to keep or start", "Voted to end"). */
  actionWords: { advanced: string; blocked: string }
  /** Whether this is the Data Center Story (its screens differ from a topic story's). */
  dataCenterStory: boolean
  /** Opens a screen of this story (keeps the place). */
  onOpenScreen: (screen: string) => void
}

const fmt = (n: number) => n.toLocaleString('en-US')
const STATUS: Record<string, string> = { enacted: 'Enacted', passed_chamber: 'Passed one chamber', pending: 'Pending', failed: 'Failed' }
const LABEL: Record<string, string> = {
  opposed: 'Public mostly opposed',
  mixed: 'Both sides spoke',
  supportive: 'Public mostly supportive',
  advanced: 'Moved it forward',
  blocked: 'Stopped or limited it',
  moratorium: 'Moratorium',
  tabled: 'Tabled or put off',
  meeting: 'Scheduled meeting',
  hearing: 'Public hearing',
}

function exampleDetail(step: ChainStepId, e: OutcomeExample) {
  if (!e.detail) return null
  if (e.detail.includes('<mark>')) return <span className="oc-quote">“{highlightSnippet(e.detail)}”</span>
  const word = step === 'bills' ? STATUS[e.detail] : LABEL[e.detail]
  return <span className="oc-tag">{word ?? e.detail}</span>
}

/**
 * What happened next (#1314): the chain from the meetings where a topic came up to what followed: the public's lean,
 * what local bodies did, the state bills, the meetings that named a bill, and what's coming up. Each step is one real
 * count, a line in words and up to three linked examples; tapping a step opens its screen. Vertical on a phone,
 * left-to-right on a wide screen. A step with no record says "No recorded … yet".
 */
export default function OutcomesChain({ topic, stateCode, city, scopeLabel, subject, actionWords, dataCenterStory, onOpenScreen }: Props) {
  const q = useTopicOutcomes(topic, stateCode, city)
  const title = (
    <p className="sc-h">
      What happened next on {subject} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading what happened next…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">What happened next could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  const steps = chainSteps(d, subject, actionWords)
  return (
    <div className="sc-block oc">
      {title}
      <ol className="oc-list">
        {steps.map((s) => {
          const ex = d.steps[s.id].examples
          const screen = stepScreen(s.id, dataCenterStory)
          return (
            <li key={s.id} className={`oc-step${s.count ? '' : ' is-empty'}`}>
              <div className="oc-head">
                <span className="oc-label">{s.label}</span>
                <span className="oc-num">{s.available ? fmt(s.count) : '—'}</span>
              </div>
              <p className="oc-line">{s.available ? s.line : 'Not available yet.'}</p>
              {ex.length > 0 && (
                <ul className="oc-examples">
                  {ex.slice(0, 3).map((e) => (
                    <li key={e.id}>
                      <span className="oc-ex-meta">
                        {[upcomingDate(e.date), [e.jurisdiction_name, e.state_code].filter(Boolean).join(', ')].filter(Boolean).join(' · ')}
                      </span>
                      {e.url ? (
                        e.url.startsWith('/') ? (
                          <Link to={e.url} className="oc-ex-title">{e.title ?? 'Open'}</Link>
                        ) : (
                          <a href={e.url} target="_blank" rel="noopener noreferrer" className="oc-ex-title">
                            {e.title ?? 'Open'}
                          </a>
                        )
                      ) : (
                        <span className="oc-ex-title">{e.title}</span>
                      )}
                      {exampleDetail(s.id, e)}
                    </li>
                  ))}
                </ul>
              )}
              {screen && s.count > 0 && (
                <button type="button" className="oc-more" onClick={() => onOpenScreen(screen)}>
                  See all →
                </button>
              )}
            </li>
          )
        })}
      </ol>
      <p className="sc-note">
        Counts are meetings, never speakers. The public&apos;s lean and what the body did are an AI (Jev) reading of each
        transcript, not official minutes. A meeting is tied to a state bill only when the transcript, a decision, the agenda
        or minutes write the bill&apos;s number, in the same state.
      </p>
    </div>
  )
}
