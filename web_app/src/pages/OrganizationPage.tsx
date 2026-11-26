import { Link, useParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import OrganizationFunding from '../components/OrganizationFunding'
import { highlightSnippet } from '../lib/highlight'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

/**
 * Organization page (#1015) at /organizations/:masterOrgId: who the organization is (from the organization master
 * and, for companies, the curated record with its own source), and where it is named in meetings and decisions,
 * each with the verbatim passage. Only recorded values are shown; a missing one is left out, never filled in.
 */
interface Mention {
  mention_kind: 'meeting' | 'decision' | string
  title: string | null
  date: string | null
  jurisdiction_name: string | null
  state_code: string | null
  url: string | null
  evidence: string | null
}

interface Profile {
  master_org_id: string
  name: string
  org_type: string | null
  org_subtype: string | null
  ein: string | null
  city: string | null
  state_code: string | null
  website_url: string | null
  first_seen_year: string | null
  last_seen_year: string | null
  record_sources: string[]
  company_roles: string[]
  aliases: string[]
  company_source: { url: string; excerpt: string; kind: string | null } | null
  mentions_total: number
  meetings: number
  decisions: number
  mentions: Mention[]
}

const ROLE_LABEL: Record<string, string> = {
  short_term_rental_platform: 'Short-term rental platform',
  developer: 'Data center developer',
  operator: 'Data center operator',
  owner: 'Data center owner',
  tenant: 'Data center tenant',
  user: 'Data center user',
  utility: 'Utility partner',
}
const SOURCE_LABEL: Record<string, string> = {
  bronze_organizations_nonprofits_irs: 'IRS exempt organizations registry',
  bronze_organizations_nonprofits_nccs: 'NCCS nonprofit filings',
  bronze_organizations_from_ai: 'Named in meeting analyses',
  bronze_locations: 'Location records',
  bronze_organizations_gov: 'Data.gov agencies',
  seed_data_center_companies: 'Curated company list (data centers)',
  seed_short_term_rental_companies: 'Curated company list (short-term rentals)',
}
const fmt = (n: number) => n.toLocaleString('en-US')
const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase())

export default function OrganizationPage() {
  const { masterOrgId = '' } = useParams<{ masterOrgId: string }>()
  const q = useQuery({
    queryKey: ['organization', masterOrgId],
    queryFn: async () => (await api.get<Profile>(`/organizations/${encodeURIComponent(masterOrgId)}`, { params: { limit: 20 } })).data,
    enabled: Boolean(masterOrgId),
    retry: (n, err: unknown) => (err as { response?: { status?: number } })?.response?.status !== 404 && n < 1,
  })

  // Later pages of "Where it was named" (the first page comes with the profile).
  const more = useInfiniteQuery({
    queryKey: ['organization', masterOrgId, 'mentions'],
    queryFn: async ({ pageParam }) =>
      (await api.get<Profile>(`/organizations/${encodeURIComponent(masterOrgId)}`, { params: { limit: 20, offset: pageParam } })).data.mentions,
    initialPageParam: 20,
    getNextPageParam: (last, pages) => (last.length === 20 ? 20 + pages.reduce((a, p) => a + p.length, 0) : undefined),
    enabled: false,
  })

  if (q.isPending) return <div className="mx-auto max-w-4xl px-4 py-12 text-stone-500">Loading…</div>
  if (q.isError) {
    const notFound = (q.error as { response?: { status?: number } })?.response?.status === 404
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <p className="text-stone-700">{notFound ? "That organization isn't in our records here." : 'This organization is unavailable right now.'}</p>
        <Link to="/search?types=organizations" className="mt-2 inline-block text-teal-700 underline">
          Search organizations
        </Link>
      </div>
    )
  }
  const o = q.data
  const place = [o.city ? titleCase(o.city) : null, o.state_code ? (STATE_CODE_TO_NAME[o.state_code] ?? o.state_code) : null].filter(Boolean).join(', ')
  const kind = o.company_roles.length
    ? o.company_roles.map((r) => ROLE_LABEL[r] ?? r).join(' · ')
    : o.org_type
      ? titleCase(o.org_type)
      : null
  const brands = o.aliases.filter((a) => a !== o.name && !a.includes(','))

  return (
    <div className="mx-auto max-w-4xl px-4 pb-16 pt-6 sm:px-6">
      <p className="font-mono text-xs uppercase tracking-widest text-teal-700">Organization</p>
      <h1 className="mt-2 font-serif text-3xl font-bold text-stone-900 sm:text-4xl">{o.name}</h1>
      {kind && <p className="mt-1 text-stone-600">{kind}</p>}

      <dl className="mt-6 grid gap-x-8 gap-y-3 rounded-xl border border-stone-200 bg-white p-5 text-sm sm:grid-cols-2">
        {brands.length > 0 && (
          <div>
            <dt className="text-stone-500">Brands</dt>
            <dd className="text-stone-900">{brands.join(', ')}</dd>
          </div>
        )}
        {o.website_url && (
          <div>
            <dt className="text-stone-500">Website</dt>
            <dd>
              <a href={o.website_url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-2">
                {o.website_url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            </dd>
          </div>
        )}
        {place && (
          <div>
            <dt className="text-stone-500">Location</dt>
            <dd className="text-stone-900">{place}</dd>
          </div>
        )}
        {o.ein && (
          <div>
            <dt className="text-stone-500">EIN</dt>
            <dd className="text-stone-900">{o.ein.length === 9 ? `${o.ein.slice(0, 2)}-${o.ein.slice(2)}` : o.ein}</dd>
          </div>
        )}
        {(o.first_seen_year || o.last_seen_year) && (
          <div>
            <dt className="text-stone-500">In our records</dt>
            <dd className="text-stone-900">{o.first_seen_year === o.last_seen_year ? o.first_seen_year : `${o.first_seen_year ?? '—'}–${o.last_seen_year ?? '—'}`}</dd>
          </div>
        )}
        {o.record_sources.length > 0 && (
          <div className="sm:col-span-2">
            <dt className="text-stone-500">Built from</dt>
            <dd className="text-stone-900">{o.record_sources.map((s) => SOURCE_LABEL[s] ?? s).join(' · ')}</dd>
          </div>
        )}
      </dl>

      {o.company_source && (
        <figure className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
          <blockquote className="italic text-stone-700">“{o.company_source.excerpt}”</blockquote>
          <figcaption className="mt-1 text-xs text-stone-500">
            Source:{' '}
            <a href={o.company_source.url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-2">
              {o.company_source.url.replace(/^https?:\/\//, '')}
            </a>
          </figcaption>
        </figure>
      )}

      {(o.mentions_total > 0 || o.company_roles.includes('short_term_rental_platform')) && (
        <section className="mt-10" aria-labelledby="org-mentions-h">
          <h2 id="org-mentions-h" className="font-serif text-2xl font-semibold text-stone-900">
            Where it was named
          </h2>
          <p className="mt-1 text-sm text-stone-500">
            {fmt(o.meetings)} {o.meetings === 1 ? 'meeting' : 'meetings'} and {fmt(o.decisions)} {o.decisions === 1 ? 'decision' : 'decisions'} name it
            {brands.length ? ` (as ${[o.name, ...brands].join(' or ')})` : ''}. A mention is the name in the record, not a claim about the company's role.
          </p>
          {o.mentions.length === 0 ? (
            <p className="mt-4 text-sm text-stone-500">Not named in any meeting or decision on record.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {[...o.mentions, ...(more.data?.pages.flat() ?? [])].map((m, i) => (
                <li key={`${m.url}-${i}`} className="rounded-xl border border-stone-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{m.mention_kind === 'decision' ? 'Decision' : 'Meeting'}</p>
                  <p className="text-sm font-semibold text-stone-900">
                    {m.url?.startsWith('/') ? (
                      <Link to={m.url} className="hover:text-teal-700">
                        {m.title ?? 'Decision'}
                      </Link>
                    ) : (
                      (m.title ?? 'Meeting')
                    )}
                  </p>
                  <p className="text-xs text-stone-500">
                    {[m.jurisdiction_name, m.state_code].filter(Boolean).join(', ')}
                    {fmtDate(m.date) ? ` · ${fmtDate(m.date)}` : ''}
                  </p>
                  {m.evidence && (
                    <blockquote className="mt-2 border-l-2 border-teal-600 pl-3 text-sm italic leading-relaxed text-stone-700">
                      “{highlightSnippet(m.evidence)}”
                    </blockquote>
                  )}
                  {m.url && !m.url.startsWith('/') && (
                    <a href={m.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm font-semibold text-teal-700">
                      Watch the meeting ↗
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
          {o.mentions_total > o.mentions.length + (more.data?.pages.flat().length ?? 0) && (more.data ? more.hasNextPage : true) && (
            <button
              type="button"
              onClick={() => (more.data ? more.fetchNextPage() : more.refetch())}
              disabled={more.isFetching}
              className="mt-4 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 hover:bg-stone-50 disabled:opacity-50"
            >
              {more.isFetching ? 'Loading…' : 'Show more'}
            </button>
          )}
        </section>
      )}

      <OrganizationFunding masterOrgId={o.master_org_id} isCompany={o.company_roles.length > 0 || o.org_type === 'company'} />
    </div>
  )
}
