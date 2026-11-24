import { useChartData } from './ChartPanel'
import StatRow from './StatRow'
import { storyStats } from '../../utils/dataStory'
import type { StoryData } from '../../utils/dataStory'
import type { ChartData } from '../../utils/stanceGame'

interface Props {
  packTitle: string
  statementCount: number
  onStart: () => void
}

/**
 * The first screen: what the challenge is and a row of large, real counts. Each count comes straight from a national
 * data-center endpoint (its own totals); a count that is missing, zero or failed to load is left out.
 */
export default function Cover({ packTitle, statementCount, onStart }: Props) {
  const useNational = (k: string) => useChartData(k, true, undefined).data as ChartData | undefined
  const data: StoryData = {
    'meeting-mentions': useNational('meeting-mentions'),
    'agenda-items': useNational('agenda-items'),
    sites: useNational('sites'),
    'job-claims': useNational('job-claims'),
  }
  const stats = storyStats(data)

  return (
    <section className="stance-cover" data-cover aria-labelledby="stance-cover-h">
      <div className="stance-cover-body">
        <p className="folio-eyebrow">The challenge · {statementCount} statements</p>
        <h1 className="stance-cover-title" id="stance-cover-h">
          {packTitle}
        </h1>
        <p className="stance-cover-lead">
          Each round shows what the public record says, then puts one statement to you. Answer agree, disagree or not sure. There is no answer
          key. Then see how people who played answered.
        </p>
        {stats.length > 0 && <StatRow stats={stats} label="What the records cover, nationally" />}
        {stats.length > 0 && <p className="stance-note">Counts for the whole country, from Open Navigator records.</p>}
        <div className="stance-nav">
          <button type="button" className="folio-btn stance-next" onClick={onStart}>
            Start the challenge →
          </button>
        </div>
      </div>
    </section>
  )
}
