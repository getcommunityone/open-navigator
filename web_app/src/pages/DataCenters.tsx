import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import CitationLink from '../components/CitationLink'
import { meetingMomentPath } from '../lib/timestamp'
import {
  fetchDataCenterAgendaItems,
  fetchDataCenterSites,
  type DataCenterAgendaItem,
  fetchJobClaims,
  type DataCenterSite,
  type JobClaim,
  type JobClaimPhase,
} from '../api/dataCenters'
import { fetchApplicationLinks, type ApplicationLink } from '../api/applicationLinks'
import {
  formatDateRange,
  formatHeadcount,
  formatIsoDate,
  meetingAttribution,
  placeScope,
  siteStatusLabel,
  verifiedLabel,
} from '../lib/dataCenterJobs'
import { expandStateName } from '../utils/formatters'
import { highlightSnippet } from '../lib/highlight'

/**
 * /data-centers — "Jobs promised" panel (issue #246, DC-1.1).
 *
 * Scope follows the site-wide rule (CLAUDE.md, "Scope Label Must Match the
 * Active Filter"): `?state=&city=` in the URL is the single authority for the
 * label, the API query, and the rendered claims. Broadening rewrites the URL.
 */
export default function DataCenters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawState = (searchParams.get('state') || '').trim() || undefined
  const cityName = (searchParams.get('city') || '').trim() || undefined

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['data-centers', 'job-claims', rawState ?? null, cityName ?? null],
    queryFn: () => fetchJobClaims({ state: rawState, city: cityName }),
  })

  // The label follows the scope the API applied (it normalizes "Alabama" to "AL"),
  // so the label and the data always name the same place.
  const stateCode = data?.scope?.state_code ?? rawState?.toUpperCase()
  const scope = placeScope(stateCode, cityName)

  const setScope = (next: { state?: string; city?: string }) => {
    const params = new URLSearchParams(searchParams)
    if (next.state) params.set('state', next.state)
    else params.delete('state')
    if (next.city) params.set('city', next.city)
    else params.delete('city')
    setSearchParams(params)
  }

  const items = data?.items ?? []
  const construction = items.filter((c) => c.phase === 'construction')
  const operations = items.filter((c) => c.phase === 'operations')

  return (
    <div className="min-h-screen bg-gray-50 py-5">
      <div className="mx-auto max-w-7xl px-4">
        <h1 className="mb-3 text-3xl font-bold text-gray-900">
          Data centers <span className="font-normal text-gray-400">· {scope.label}</span>
        </h1>

        <ScopeControl
          stateCode={stateCode}
          cityName={cityName}
          activeLevel={scope.level}
          onPick={setScope}
        />

        <section aria-labelledby="jobs-promised-heading" className="mt-4">
          <h2 id="jobs-promised-heading" className="mb-1 text-xl font-semibold text-gray-900">
            Jobs promised
          </h2>
          <p className="mb-4 text-sm text-gray-600">
            What was said in public meetings about data-center jobs, quoted from the record.
            Construction and operations jobs are listed separately.
          </p>

          {isLoading ? (
            <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
              Loading jobs claims for {scope.label}…
            </div>
          ) : isError ? (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Couldn&apos;t load jobs claims.{' '}
              {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}{' '}
              <button type="button" onClick={() => refetch()} className="font-medium underline">
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
              No jobs claims found in meetings for {scope.label} yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <PhaseColumn
                phase="construction"
                claims={construction}
                total={data?.totals?.construction ?? construction.length}
                scopeLabel={scope.label}
              />
              <PhaseColumn
                phase="operations"
                claims={operations}
                total={data?.totals?.operations ?? operations.length}
                scopeLabel={scope.label}
              />
            </div>
          )}
        </section>

        <AgendaSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />

        <SitesSection rawState={rawState} cityName={cityName} />

        <ApplySection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />
      </div>
    </div>
  )
}

/**
 * "On the agenda" (DC-4.2, #250): agendas that mention a data center, upcoming meetings
 * first so residents can attend before the vote. Each item quotes the agenda with the
 * matched words highlighted (the site-wide match-evidence rule), from the server's
 * ts_headline excerpt rendered by highlightSnippet (React-escaped, no innerHTML).
 */
function AgendaSection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'agenda-items', rawState ?? null, cityName ?? null],
    queryFn: () => fetchDataCenterAgendaItems({ state: rawState, city: cityName }),
  })
  const items = data?.items ?? []
  const upcoming = items.filter((i) => i.is_upcoming)
  const past = items.filter((i) => !i.is_upcoming)
  return (
    <section aria-labelledby="agenda-heading" className="mt-6">
      <h2 id="agenda-heading" className="mb-1 text-xl font-semibold text-gray-900">
        On the agenda
      </h2>
      <p className="mb-3 text-sm text-gray-600">
        Meeting agendas in {scopeLabel} that mention a data center, quoted from the agenda. Upcoming meetings come first,
        so you can attend before the vote.
      </p>
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading agendas for {scopeLabel}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load agendas.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No agendas mentioning a data center for {scopeLabel} yet.
        </div>
      ) : (
        <>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-700">
            Coming up{data?.counts ? ` (${data.counts.upcoming})` : ''}
          </h3>
          {upcoming.length === 0 ? (
            <p className="mb-4 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
              No upcoming agendas mention a data center for {scopeLabel}.
            </p>
          ) : (
            <ul className="mb-4 space-y-3">
              {upcoming.map((item) => (
                <AgendaCard key={item.data_center_agenda_item_id} item={item} />
              ))}
            </ul>
          )}
          {past.length > 0 && (
            <>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-700">
                Earlier meetings{data?.counts ? ` (${data.counts.past})` : ''}
              </h3>
              <ul className="space-y-3">
                {past.map((item) => (
                  <AgendaCard key={item.data_center_agenda_item_id} item={item} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  )
}

function AgendaCard({ item }: { item: DataCenterAgendaItem }) {
  const when = formatIsoDate(item.doc_date)
  const where = [item.jurisdiction_name, item.state_code].filter(Boolean).join(', ')
  return (
    <li className={`rounded-lg border bg-white p-4 shadow-sm ${item.is_upcoming ? 'border-primary-200' : 'border-gray-200'}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-gray-900">
          {item.meeting_title || 'Meeting'}
          {where && <span className="font-normal text-gray-600"> · {where}</span>}
        </p>
        <p className={`text-sm ${item.is_upcoming ? 'font-semibold text-primary-700' : 'text-gray-500'}`}>
          {when ?? 'Date not listed'}
          {!item.is_upcoming && when && ' · already met'}
        </p>
      </div>
      <blockquote className="mt-2 line-clamp-4 border-l-4 border-primary-300 pl-3 text-sm text-gray-800">
        {highlightSnippet(item.evidence)}
      </blockquote>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {item.mentions_zoning_or_utility && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">Zoning or utility item</span>
        )}
        {item.site_name && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-700">Site: {item.site_name}</span>}
        {item.document_url && (
          <a href={item.document_url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary-700 hover:underline">
            Read the agenda
          </a>
        )}
      </div>
    </li>
  )
}

/**
 * "Sites" (DC-4.1, #249): data center sites from Epoch AI (CC BY 4.0), with status and
 * source. Sites the source stopped listing stay, labeled. The source has no city field,
 * so this section narrows by state only, and its own label says which scope it shows
 * (CLAUDE.md, scope label rule) instead of borrowing the page's city.
 */
function SitesSection({ rawState, cityName }: { rawState?: string; cityName?: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'sites', rawState ?? null],
    queryFn: () => fetchDataCenterSites({ state: rawState }),
  })
  const sites = data?.items ?? []
  const stateName = data?.scope?.state ?? (rawState ? expandStateName(rawState) || rawState : undefined)
  const sitesScope = stateName ?? 'National'
  const counts = data?.counts
  return (
    <section aria-labelledby="sites-heading" className="mt-6">
      <h2 id="sites-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Sites <span className="font-normal text-gray-400">· {sitesScope}</span>
      </h2>
      <p className="mb-2 text-sm text-gray-600">
        Large AI data center sites tracked by Epoch AI, with each site&apos;s status. Sites the source stops listing
        stay here, marked, so they don&apos;t quietly disappear.
      </p>
      {cityName && (
        <p className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          This source doesn&apos;t give cities, so these are all tracked sites in {sitesScope}, not just {cityName}.
        </p>
      )}
      {counts && sites.length > 0 && (
        <p className="mb-3 text-xs text-gray-600">
          {counts.planned} planned · {counts.under_construction} under construction · {counts.operating} operating
          {counts.no_longer_listed > 0 && ` · ${counts.no_longer_listed} no longer listed`}
        </p>
      )}
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading sites for {sitesScope}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load sites.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : sites.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No tracked sites for {sitesScope} yet.
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {sites.map((site) => (
            <SiteCard key={site.data_center_site_id} site={site} />
          ))}
        </ul>
      )}
      {sites.length > 0 && (
        <p className="mt-2 text-xs text-gray-500">
          Source:{' '}
          <a href={sites[0].source_url} target="_blank" rel="noopener noreferrer" className="underline">
            {sites[0].attribution}
          </a>
        </p>
      )}
    </section>
  )
}

function SiteCard({ site }: { site: DataCenterSite }) {
  const gone = site.status === 'no_longer_listed'
  const place = [site.address, site.state_code && !site.address?.includes(site.state_code) ? site.state_code : null]
    .filter(Boolean)
    .join(', ')
  return (
    <li className={`rounded-lg border bg-white p-4 shadow-sm ${gone ? 'border-dashed border-gray-300 opacity-90' : 'border-gray-200'}`}>
      <p className="font-semibold text-gray-900">{site.site_name}</p>
      {(site.owner || site.users) && (
        <p className="text-sm text-gray-600">
          {[site.owner && `Owner: ${site.owner}`, site.users && `Used by: ${site.users}`].filter(Boolean).join(' · ')}
        </p>
      )}
      {place && <p className="text-xs text-gray-500">{place}</p>}
      <p className={`mt-2 text-sm font-medium ${gone ? 'text-gray-600' : 'text-gray-900'}`}>
        {siteStatusLabel(site.status, site.last_known_status, site.last_seen_on)}
      </p>
      {site.construction_note && <p className="mt-1 text-xs italic text-gray-600">“{site.construction_note}”</p>}
    </li>
  )
}

/**
 * "Apply for jobs" (DC-1.3, #248): application links admins keep, for the same
 * scope as the page. Links whose page is gone are left out by the API; each link
 * says when it was last verified, and links not verified in 30 days are flagged.
 */
function ApplySection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'application-links', rawState ?? null, cityName ?? null],
    queryFn: () => fetchApplicationLinks({ state: rawState, city: cityName }),
  })
  const links = data?.items ?? []
  return (
    <section aria-labelledby="apply-heading" className="mt-6">
      <h2 id="apply-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Apply for jobs
      </h2>
      <p className="mb-4 text-sm text-gray-600">
        Application links for data center projects, checked so you aren&apos;t sent to a posting that closed.
      </p>
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading application links for {scopeLabel}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load application links.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : links.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No application links for {scopeLabel} yet.
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {links.map((link) => (
            <ApplyLinkCard key={link.job_application_link_id} link={link} />
          ))}
        </ul>
      )}
    </section>
  )
}

function ApplyLinkCard({ link }: { link: ApplicationLink }) {
  const place = [link.city, link.state ?? link.state_code].filter(Boolean).join(', ')
  return (
    <li className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="font-semibold text-gray-900">{link.project_name}</p>
      {(link.employer || place) && (
        <p className="text-sm text-gray-600">{[link.employer, place].filter(Boolean).join(' · ')}</p>
      )}
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="mt-2 inline-block rounded bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
      >
        Apply
      </a>
      <p className={`mt-2 text-xs ${link.is_stale ? 'font-medium text-amber-700' : 'text-gray-500'}`}>
        {link.is_stale && <span aria-hidden="true">⚠ </span>}
        {verifiedLabel(link.last_verified_at, link.is_stale)}
      </p>
    </li>
  )
}

interface ScopeControlProps {
  stateCode?: string
  cityName?: string
  activeLevel: 'national' | 'state' | 'city'
  onPick: (next: { state?: string; city?: string }) => void
}

/** One-click broaden: city -> state -> national. Only levels that apply are shown. */
function ScopeControl({ stateCode, cityName, activeLevel, onPick }: ScopeControlProps) {
  if (activeLevel === 'national') return null
  const btn = (on: boolean) =>
    `rounded-md px-3 py-1 font-medium transition-colors ${
      on ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
    }`
  return (
    <div className="inline-flex items-center gap-1 rounded-lg bg-gray-100 p-1 text-sm" aria-label="Place scope">
      {cityName && (
        <button
          type="button"
          aria-pressed={activeLevel === 'city'}
          onClick={() => onPick({ state: stateCode, city: cityName })}
          className={btn(activeLevel === 'city')}
        >
          📍 {cityName}
        </button>
      )}
      {stateCode && (
        <button
          type="button"
          aria-pressed={activeLevel === 'state'}
          onClick={() => onPick({ state: stateCode })}
          className={btn(activeLevel === 'state')}
          title={`All of ${expandStateName(stateCode)}`}
        >
          All of {stateCode}
        </button>
      )}
      <button type="button" aria-pressed={false} onClick={() => onPick({})} className={btn(false)}>
        National
      </button>
    </div>
  )
}

const PHASE_TITLE: Record<JobClaimPhase, string> = {
  construction: 'Construction jobs',
  operations: 'Operations jobs',
}

interface PhaseColumnProps {
  phase: JobClaimPhase
  claims: JobClaim[]
  /** Claims in this phase for the whole scope (the API's totals), not just this page. */
  total: number
  scopeLabel: string
}

function PhaseColumn({ phase, claims, total, scopeLabel }: PhaseColumnProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-lg font-semibold text-gray-900">
        {PHASE_TITLE[phase]}{' '}
        <span className="text-sm font-normal text-gray-500">
          ({total.toLocaleString()} {total === 1 ? 'claim' : 'claims'}
          {claims.length < total ? `, showing the latest ${claims.length.toLocaleString()}` : ''})
        </span>
      </h3>
      {claims.length === 0 ? (
        <p className="text-sm text-gray-500">
          No {phase} jobs claims found in meetings for {scopeLabel} yet.
        </p>
      ) : (
        <ul className="space-y-4">
          {claims.map((c) => (
            <li key={c.job_claim_id}>
              <ClaimCard claim={c} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ClaimCard({ claim }: { claim: JobClaim }) {
  const headcount = formatHeadcount(claim.headcount_low, claim.headcount_high)
  const unknownHeadcount = claim.headcount_low == null && claim.headcount_high == null
  const meetingId = String(claim.event_meeting_id)
  const atMeeting = meetingAttribution(claim.body_name)
  return (
    <article className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className={`text-lg font-bold ${unknownHeadcount ? 'text-gray-500' : 'text-gray-900'}`}>{headcount}</p>
        <p className="text-xs text-gray-500">{formatDateRange(claim.starts_on, claim.ends_on)}</p>
      </div>
      {claim.project_name && <p className="mt-1 text-sm font-medium text-gray-700">{claim.project_name}</p>}
      <blockquote className="mt-2 border-l-4 border-primary-300 pl-3 text-sm italic text-gray-800">
        {claim.quote}
      </blockquote>
      {/* DC-1.2 (#247): who said it (with role), when, and the moment in the recording. */}
      <div className="mt-2">
        <CitationLink
          meetingId={meetingId}
          startSeconds={claim.start_seconds ?? null}
          speakerName={claim.speaker_name}
          speakerRole={claim.speaker_role}
          meetingDate={claim.meeting_date}
        />
      </div>
      <p className="mt-1 flex flex-wrap gap-x-3 text-xs text-gray-600">
        <Link to={meetingMomentPath(meetingId, null)} className="font-medium text-primary-700 hover:underline">
          {atMeeting}
        </Link>
        {claim.person_id && claim.speaker_name && (
          <Link to={`/person/${encodeURIComponent(claim.person_id)}`} className="font-medium text-primary-700 hover:underline">
            More from {claim.speaker_name}
          </Link>
        )}
      </p>
    </article>
  )
}
