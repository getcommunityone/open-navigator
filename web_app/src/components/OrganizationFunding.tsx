import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

/**
 * Funds / Funded by on the organization page (#1073), from GET /api/organizations/{id}/funding (company_grant).
 * Every dollar figure is what the foundation's IRS 990 Schedule I reports, summed by the API; a blank amount stays
 * blank. Nothing is shown as a figure when there is no grant on record.
 */
interface YearTotal {
  tax_year: string | null
  amount: number | null
  grants: number
}
interface GrantLine {
  grant_id: string
  amount: number | null
  purpose: string | null
  tax_year: string | null
  source_url: string | null
}
interface FundsEntry {
  grantee_name: string
  grantee_ein: string | null
  grantee_master_org_id: string | null
  grantee_city: string | null
  grantee_state_code: string | null
  foundation_name: string
  foundation_ein: string
  total_amount: number | null
  grants: number
  by_year: YearTotal[]
  top_grants: GrantLine[]
}
interface FundedByEntry {
  company_key: string
  company_name: string
  master_org_id: string
  foundation_name: string
  foundation_ein: string
  foundation_master_org_id: string | null
  relationship: string | null
  foundation_source_url: string | null
  total_amount: number | null
  grants: number
  by_year: YearTotal[]
  top_grants: GrantLine[]
}
interface Foundation {
  company_key: string | null
  company_name: string | null
  foundation_name: string | null
  foundation_ein: string | null
  foundation_master_org_id: string | null
  relationship: string | null
  foundation_source_url: string | null
}
interface Funding {
  master_org_id: string
  foundations: Foundation[]
  funds_total: number | null
  funds_grants: number
  funds_by_year: YearTotal[]
  funds: FundsEntry[]
  funded_by: FundedByEntry[]
}

const RELATIONSHIP_LABEL: Record<string, string> = {
  founded_by_company: 'founded by',
  governed_by_company: 'governed by executives of',
  controls_company: 'the nonprofit that controls',
}
const usd = (n: number | null) => (n === null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }))
const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
const titleCase = (s: string) => s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
const fmtEin = (e: string) => (e.length === 9 ? `${e.slice(0, 2)}-${e.slice(2)}` : e)

function Years({ years }: { years: YearTotal[] }) {
  if (!years.length) return null
  return (
    <p className="mt-1 text-xs text-stone-500">
      {years.map((y) => `${y.tax_year ?? 'Year not stated'}: ${usd(y.amount)}`).join(' · ')}
    </p>
  )
}

function Grants({ grants }: { grants: GrantLine[] }) {
  if (!grants.length) return null
  return (
    <ul className="mt-2 space-y-1 text-xs text-stone-600">
      {grants.map((g) => (
        <li key={g.grant_id}>
          {usd(g.amount)}
          {g.tax_year ? ` (${g.tax_year})` : ''}
          {g.purpose ? ` — “${g.purpose}”` : ''}
          {g.source_url && (
            <>
              {' '}
              <a href={g.source_url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-2">
                990 filing
              </a>
            </>
          )}
        </li>
      ))}
    </ul>
  )
}

export default function OrganizationFunding({ masterOrgId, isCompany }: { masterOrgId: string; isCompany: boolean }) {
  const q = useQuery({
    queryKey: ['organization', masterOrgId, 'funding'],
    queryFn: async () => (await api.get<Funding>(`/organizations/${encodeURIComponent(masterOrgId)}/funding`)).data,
    enabled: Boolean(masterOrgId),
    retry: 1,
  })

  if (q.isPending) return <p className="mt-10 text-sm text-stone-500">Loading funding…</p>
  if (q.isError) return <p className="mt-10 text-sm text-stone-500">Funding records are unavailable right now.</p>
  const f = q.data
  const showFunds = isCompany || f.funds.length > 0

  return (
    <>
      {showFunds && (
        <section className="mt-10" aria-labelledby="org-funds-h">
          <h2 id="org-funds-h" className="font-serif text-2xl font-semibold text-stone-900">
            Funds
          </h2>
          {f.foundations.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">
              No foundation of this company is in our IRS 990 grant records. Our grant records cover nonprofits that file a 990;
              private foundations that file a 990-PF aren't loaded yet.
            </p>
          ) : (
            <>
              <p className="mt-1 text-sm text-stone-500">
                Grants reported on the IRS 990 of{' '}
                {f.foundations.map((fd, i) => (
                  <span key={`${fd.foundation_ein}-${i}`}>
                    {i > 0 ? ', ' : ''}
                    {fd.foundation_name}
                    {fd.foundation_ein ? ` (EIN ${fmtEin(fd.foundation_ein)})` : ''}
                    {fd.relationship && fd.company_name ? `, ${RELATIONSHIP_LABEL[fd.relationship] ?? 'tied to'} ${fd.company_name}` : ''}
                    {fd.foundation_source_url && (
                      <>
                        {' '}
                        <a href={fd.foundation_source_url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-2">
                          source
                        </a>
                      </>
                    )}
                  </span>
                ))}
                . {plural(f.funds_grants, 'grant', 'grants')}
                {f.funds_total !== null ? `, ${usd(f.funds_total)} in all` : ''}.
              </p>
              <Years years={f.funds_by_year} />
              {f.funds.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">No grants on record.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {f.funds.map((g) => (
                    <li key={`${g.grantee_master_org_id ?? g.grantee_name}-${g.foundation_ein}`} className="rounded-xl border border-stone-200 bg-white p-4">
                      <p className="text-sm font-semibold text-stone-900">
                        {g.grantee_master_org_id ? (
                          <Link to={`/organizations/${encodeURIComponent(g.grantee_master_org_id)}`} className="hover:text-teal-700">
                            {titleCase(g.grantee_name)}
                          </Link>
                        ) : (
                          titleCase(g.grantee_name)
                        )}
                      </p>
                      <p className="text-xs text-stone-500">
                        {[g.grantee_city ? titleCase(g.grantee_city) : null, g.grantee_state_code].filter(Boolean).join(', ')}
                        {g.grantee_city || g.grantee_state_code ? ' · ' : ''}
                        {usd(g.total_amount)} in {plural(g.grants, 'grant', 'grants')}
                      </p>
                      <Years years={g.by_year} />
                      <Grants grants={g.top_grants} />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      )}

      <section className="mt-10" aria-labelledby="org-funded-by-h">
        <h2 id="org-funded-by-h" className="font-serif text-2xl font-semibold text-stone-900">
          Funded by
        </h2>
        {f.funded_by.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500">
            No grants on record from the foundations of the companies we track.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {f.funded_by.map((c) => (
              <li key={c.foundation_ein} className="rounded-xl border border-stone-200 bg-white p-4">
                <p className="text-sm font-semibold text-stone-900">
                  <Link to={`/organizations/${encodeURIComponent(c.master_org_id)}`} className="hover:text-teal-700">
                    {c.company_name}
                  </Link>
                  <span className="font-normal text-stone-600"> through {c.foundation_name}</span>
                </p>
                <p className="text-xs text-stone-500">
                  {usd(c.total_amount)} in {plural(c.grants, 'grant', 'grants')}, as reported on the foundation's IRS 990
                  {c.foundation_source_url && (
                    <>
                      {' · '}
                      <a href={c.foundation_source_url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-2">
                        how it's tied to {c.company_name}
                      </a>
                    </>
                  )}
                </p>
                <Years years={c.by_year} />
                <Grants grants={c.top_grants} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
