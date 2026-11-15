import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import CitationLink from '../components/CitationLink'
import { meetingMomentPath } from '../lib/timestamp'
import { fetchJobClaims, type JobClaim, type JobClaimPhase } from '../api/dataCenters'
import {
  formatDateRange,
  formatHeadcount,
  meetingAttribution,
  placeScope,
} from '../lib/dataCenterJobs'
import { expandStateName } from '../utils/formatters'

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
      </div>
    </div>
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
      <p className="mt-1 text-xs text-gray-600">
        <Link to={meetingMomentPath(meetingId, null)} className="font-medium text-primary-700 hover:underline">
          {atMeeting}
        </Link>
      </p>
    </article>
  )
}
