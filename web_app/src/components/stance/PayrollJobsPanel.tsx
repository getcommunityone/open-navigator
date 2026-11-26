import type { JobClaimsResponse } from '../../api/dataCenters'

/**
 * The jobs screen's record of actual jobs (#1019): BLS payroll employment in the industry that includes data centers
 * (NAICS 518210, private, annual average), for the scope's state and the nation, then where data center jobs are
 * tracked. A figure BLS withheld shows as "withheld", never a number. Job boards are cited, not scraped.
 */
const fmt = (n: number) => n.toLocaleString('en-US')
const ACCESS: Record<string, string> = {
  public_data: 'Loaded here',
  prohibited_by_terms: 'Its terms forbid automated collection; not pulled',
  not_pulled: 'Cited; not pulled',
}
const change = (pct: number) => `${pct > 0 ? '+' : ''}${pct}% from the year before`

export default function PayrollJobsPanel({ data }: { data: JobClaimsResponse }) {
  const rows = data.employment ?? []
  const sources = data.sources ?? []
  if (rows.length === 0 && sources.length === 0) return null
  const year = rows[0]?.year
  return (
    <figure className="stance-payroll">
      {rows.length > 0 && (
        <>
          <figcaption className="stance-payroll-head">
            Payroll jobs in the industry that includes data centers{year ? `, ${year}` : ''}
          </figcaption>
          <ul className="stance-payroll-rows">
            {rows.map((r) => (
              <li key={`${r.area_level}-${r.area_name}`}>
                <span className="stance-payroll-place">{r.area_name}</span>
                {r.disclosed && r.employment != null ? (
                  <>
                    <span className="stance-payroll-n">{fmt(r.employment)} jobs</span>
                    <span className="stance-payroll-meta">
                      {[
                        r.establishments != null ? `${fmt(r.establishments)} employers` : null,
                        r.avg_annual_pay != null ? `average pay $${fmt(r.avg_annual_pay)}` : null,
                        r.employment_change_pct != null ? change(r.employment_change_pct) : null,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </>
                ) : (
                  <span className="stance-payroll-meta">Withheld by BLS to protect an employer's data.</span>
                )}
              </li>
            ))}
          </ul>
          <p className="stance-note">
            Source:{' '}
            <a href={rows[0]!.source_url} target="_blank" rel="noopener noreferrer">
              BLS Quarterly Census of Employment and Wages
            </a>
            , NAICS 518210 (computing infrastructure, data processing and web hosting), private employers. That industry
            includes data centers and is broader than them.
          </p>
        </>
      )}
      {sources.length > 0 && (
        <details className="stance-map-table">
          <summary>Where data center jobs are tracked</summary>
          <ul className="stance-payroll-sources">
            {sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.name}
                </a>
                {s.description && <q className="stance-payroll-desc">{s.description}</q>}
                <span className="stance-payroll-access">{ACCESS[s.automated_access] ?? s.automated_access}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </figure>
  )
}
