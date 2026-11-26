import { useMemo } from 'react'
import type { DataCenterPositionsResponse, PositionQuote } from '../../api/dataCenters'
import { POSITIONS_NOT_LOADED, positionFigures, positionsCaption, positionsLoaded, type LoadState, type StoryScope } from '../../utils/dataStory'
import { chartSpec, fmt } from '../../utils/stanceGame'
import { Dots } from './ChartPanel'
import { SideColumn, type Passage } from './SidesBlock'

interface Props {
  data: DataCenterPositionsResponse | null | undefined
  status: LoadState
  scope: StoryScope
  /** The id of the heading that names the block (the hub's "Who spoke up"; the story screen's headline). */
  labelledBy?: string
  /** Also list a few of the speakers' own words on each side (the story's screen; the hub stays short). */
  quotes?: boolean
}

const toPassage = (q: PositionQuote): Passage => ({
  quote: q.quote,
  speakerName: q.speaker_display_name ?? null,
  speakerRole: q.speaker_role,
  jurisdictionName: [q.jurisdiction_name, q.state_code].filter(Boolean).join(', '),
  meetingDate: q.meeting_date,
  videoUrl: q.video_url,
  startSeconds: q.start_seconds,
  about: q.decision_headline,
})

/**
 * Who spoke up (#930): five figures (spoke for, spoke against, asked a question, votes for, votes against) and one dot chart,
 * one dot per speaker (or per stated number of speakers). Every figure is a whole-scope total from the API. A figure with no
 * data behind it reads "not recorded" with the reason, never 0. While the table is not in the database the block is one quiet
 * line.
 */
export default function PositionsBlock({ data, status, scope, labelledBy, quotes = false }: Props) {
  const stateName = scope.stateName
  const spec = useMemo(() => chartSpec('positions', data, stateName), [data, stateName])
  if (status === 'loading') {
    return (
      <p className="folio-muted" role="status">
        Loading who spoke up…
      </p>
    )
  }
  const figures = positionFigures(data)
  if (!figures || !positionsLoaded(data)) {
    return (
      <p className="stance-note stance-voices-off" data-testid="positions-off">
        {POSITIONS_NOT_LOADED}
      </p>
    )
  }
  const reasons = [...new Set(figures.map((f) => f.reason).filter((r): r is string => r != null))]
  const sides = [
    { title: 'Spoke for', items: data.quotes.for.map(toPassage) },
    { title: 'Spoke against', items: data.quotes.against.map(toPassage) },
    { title: 'Asked a question', items: data.quotes.question.map(toPassage) },
  ].filter((s) => s.items.length > 0)
  return (
    <div className="stance-voices" data-testid="positions" aria-labelledby={labelledBy} role={labelledBy ? 'group' : undefined}>
      <dl className="stance-voices-figures">
        {figures.map((f) => (
          <div key={f.key} data-figure={f.key} className={f.value == null ? 'is-missing' : undefined}>
            <dt>{f.label}</dt>
            <dd>{f.value == null ? 'not recorded' : fmt(f.value)}</dd>
          </div>
        ))}
      </dl>
      {reasons.map((r) => (
        <p className="stance-note" key={r}>
          {r}
        </p>
      ))}
      {spec && (
        <figure className="stance-voices-fig" aria-label={spec.title}>
          <Dots spec={spec} />
          <figcaption className="stance-note">{spec.dotMeans}</figcaption>
        </figure>
      )}
      <p className="stance-note stance-voices-caption">{positionsCaption(data, scope)}</p>
      {quotes && sides.length > 0 && (
        <div className="stance-sides stance-voices-quotes" data-testid="positions-quotes" data-lenis-prevent>
          {sides.map((s) => (
            <SideColumn key={s.title} title={s.title} items={s.items} />
          ))}
        </div>
      )}
    </div>
  )
}
