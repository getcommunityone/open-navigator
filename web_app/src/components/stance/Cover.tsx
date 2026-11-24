import { useChartData } from './ChartPanel'
import Odometer from './Odometer'
import type {
  DataCenterAgendaItemsResponse,
  DataCenterMeetingMentionsResponse,
  DataCenterSitesResponse,
  JobClaimsResponse,
} from '../../api/dataCenters'

interface Props {
  packTitle: string
  statementCount: number
  onStart: () => void
}

interface Stat {
  key: string
  value: number
  label: string
}

/**
 * The first screen: what the game is and a row of large, real counts. Each count comes straight from a national
 * data-center endpoint (its own totals); a count that is missing, zero or failed to load is left out.
 */
export default function Cover({ packTitle, statementCount, onStart }: Props) {
  const mentions = useChartData('meeting-mentions', true, undefined).data as DataCenterMeetingMentionsResponse | undefined
  const agendas = useChartData('agenda-items', true, undefined).data as DataCenterAgendaItemsResponse | undefined
  const sites = useChartData('sites', true, undefined).data as DataCenterSitesResponse | undefined
  const claims = useChartData('job-claims', true, undefined).data as JobClaimsResponse | undefined

  const siteTotal = sites?.counts
    ? sites.counts.planned + sites.counts.under_construction + sites.counts.operating + sites.counts.no_longer_listed + sites.counts.status_not_published
    : 0
  const stats: Stat[] = [
    { key: 'meetings', value: mentions?.counts?.meetings ?? 0, label: 'meetings where a data center came up' },
    { key: 'passages', value: mentions?.counts?.passages ?? 0, label: 'meeting passages quoted' },
    { key: 'agendas', value: agendas?.counts ? agendas.counts.upcoming + agendas.counts.past : 0, label: 'meeting agendas that name one' },
    { key: 'sites', value: siteTotal, label: 'data center sites on record' },
    { key: 'claims', value: (claims?.totals?.construction ?? 0) + (claims?.totals?.operations ?? 0), label: 'jobs claims made in meetings' },
  ].filter((s) => s.value > 0)

  return (
    <section className="stance-cover" data-cover aria-labelledby="stance-cover-h">
      <div className="stance-cover-body">
        <p className="folio-eyebrow">{packTitle} · {statementCount} statements</p>
        <h1 className="stance-cover-title" id="stance-cover-h">
          Where do you stand?
        </h1>
        <p className="stance-cover-lead">
          Each round shows what the public record says, then puts one statement to you. Answer agree, disagree or not sure. There is no answer
          key. Then see how people who played answered.
        </p>
        {stats.length > 0 && (
          <dl className="stance-stats" aria-label="What the records cover, nationally">
            {stats.map((s) => (
              <div key={s.key}>
                <dt>{s.label}</dt>
                <dd>
                  <Odometer text={s.value.toLocaleString('en-US')} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        {stats.length > 0 && <p className="stance-note">Counts for the whole country, from Open Navigator records.</p>}
        <div className="stance-nav">
          <button type="button" className="folio-btn stance-next" onClick={onStart}>
            Start round one →
          </button>
        </div>
      </div>
    </section>
  )
}
