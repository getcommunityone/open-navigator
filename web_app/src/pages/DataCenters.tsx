import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import CitationLink from '../components/CitationLink'
import { meetingMomentPath } from '../lib/timestamp'
import {
  fetchAreaConcerns,
  fetchCommunityEvents,
  fetchDataCenterProjects,
  type CommunityEvent,
  type DataCenterProject,
  fetchDataCenterAgendaItems,
  fetchDataCenterHearings,
  type DataCenterHearing,
  fetchDataCenterMeetingMentions,
  fetchDataCenterSites,
  type DataCenterAgendaItem,
  type DataCenterMeetingMention,
  fetchJobClaims,
  type DataCenterSite,
  type JobClaim,
  type JobClaimPhase,
} from '../api/dataCenters'
import { fetchApplicationLinks, type ApplicationLink } from '../api/applicationLinks'
import {
  communityEventKindLabel,
  figureLabel,
  timelineStageLabel,
  formatDateRange,
  formatHeadcount,
  concernLabel,
  concernSummary,
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

  const placeQuery = stateCode ? `?state=${encodeURIComponent(stateCode)}${cityName ? `&city=${encodeURIComponent(cityName)}` : ''}` : ''
  const items = data?.items ?? []
  const construction = items.filter((c) => c.phase === 'construction')
  const operations = items.filter((c) => c.phase === 'operations')

  return (
    <div className="min-h-screen page-bg py-5">
      <div className="mx-auto max-w-7xl px-4">
        <h1 className="mb-3 text-3xl font-bold text-gray-900">
          Data centers <span className="font-normal text-gray-400">· {scope.label}</span>
        </h1>

        <p className="mb-3 text-sm">
          <Link
            to={`/stories/data-centers${placeQuery}`}
            className="font-medium text-primary-700 underline hover:text-primary-900"
          >
            Read the Data Center Story
          </Link>{' '}
          <span className="text-gray-600">The records on this page as a scrolling story.</span>{' '}
          <Link
            to={`/challenge/data-centers${placeQuery}`}
            className="font-medium text-primary-700 underline hover:text-primary-900"
          >
            Take the Data Center Challenge
          </Link>{' '}
          <span className="text-gray-600">Seven statements, and how people who played answered.</span>
        </p>

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

        <HearingsSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />
        <AgendaSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />

        <MeetingMentionsSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />

        <ProjectsSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />

        <CommunityEventsSection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />

        <SitesSection rawState={rawState} cityName={cityName} />

        <ApplySection rawState={rawState} cityName={cityName} scopeLabel={scope.label} />
      </div>
    </div>
  )
}

/**
 * "Hearings coming up" (#955): upcoming data center hearings whose OFFICIAL page (a government
 * agenda, notice or project page) states the date together with the data center item. Leads from
 * research lists that no official page backs up are never shown. Each card quotes the official
 * page with the matched words highlighted (server ts_headline -> highlightSnippet, React-escaped)
 * and links to it. Same ?state=&city= scope as the rest of the page.
 */
function HearingsSection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'hearings', rawState ?? null, cityName ?? null],
    queryFn: () => fetchDataCenterHearings({ state: rawState, city: cityName, when: 'upcoming' }),
  })
  // Not loaded, or nothing verified in scope: stay quiet; "On the agenda" below covers the place.
  if (isLoading || data?.available === false || (!isError && (data?.items ?? []).length === 0)) return null
  return (
    <section aria-labelledby="hearings-heading" className="mt-6">
      <h2 id="hearings-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Hearings coming up{data?.counts?.upcoming != null ? ` (${data.counts.upcoming})` : ''}
      </h2>
      <p className="mb-3 text-sm text-gray-600">
        Upcoming data center hearings in {scopeLabel}, each listed on the government&apos;s own page, which is quoted and
        linked. Dates can change; check the notice before you go.
      </p>
      {isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load hearings.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : (
        <ul className="space-y-3">
          {(data?.items ?? []).map((h) => (
            <HearingCard key={h.data_center_hearing_id} hearing={h} />
          ))}
        </ul>
      )}
    </section>
  )
}

function HearingCard({ hearing }: { hearing: DataCenterHearing }) {
  const when = formatIsoDate(hearing.meeting_date)
  const where = [hearing.jurisdiction_name, hearing.state_code].filter(Boolean).join(', ')
  return (
    <li className="rounded-lg border border-primary-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-gray-900" title="Body as named by the research lead; the quote below is the government's page">
          {hearing.body_name || 'Hearing'}
          {where && <span className="font-normal text-gray-600"> · {where}</span>}
        </p>
        <p className="text-sm font-semibold text-primary-700">
          {when ?? 'Date not listed'}
          {hearing.tentative && (
            <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">Tentative</span>
          )}
        </p>
      </div>
      {hearing.topic && (
        <p className="mt-1 text-sm text-gray-700">
          <span className="text-gray-500">From the research lead:</span> {hearing.topic}
        </p>
      )}
      {hearing.evidence && (
        <blockquote className="mt-2 line-clamp-6 border-l-4 border-primary-300 pl-3 text-sm text-gray-800">
          {highlightSnippet(hearing.evidence)}
        </blockquote>
      )}
      <div className="mt-2 text-xs">
        <a href={hearing.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary-700 hover:underline">
          Read the official notice{hearing.source_name ? ` (${hearing.source_name})` : ''}
        </a>
      </div>
    </li>
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
  const concerns = useQuery({
    queryKey: ['data-centers', 'concerns', rawState ?? null, cityName ?? null],
    queryFn: () => fetchAreaConcerns({ state: rawState, city: cityName }),
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
      <ConcernLine
        scopeLabel={scopeLabel}
        isNational={!rawState && !cityName}
        area={concerns.data?.items ?? []}
        national={concerns.data?.national ?? []}
        loaded={concerns.isSuccess}
      />
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

/**
 * "What residents here raise most" (DC-4.3, #251), from objections recorded in the
 * area's own meetings, with the national figure beside it. Real counts only; with no
 * recorded objections it says so, and agenda items are ranked by date alone.
 */
function ConcernLine({
  scopeLabel,
  isNational,
  area,
  national,
  loaded,
}: {
  scopeLabel: string
  isNational: boolean
  area: { concern: string; mention_count: number; objection_count: number; is_dominant: boolean; jurisdiction_name?: string | null }[]
  national: { concern: string; mention_count: number; objection_count: number }[]
  loaded: boolean
}) {
  if (!loaded) return null
  const top = area.find((c) => c.is_dominant) ?? null
  const topNational = national[0] ?? null
  const local = concernSummary(top)
  const nat = concernSummary(topNational)
  if (!local && !nat) return null
  return (
    <p className="mb-3 rounded border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700">
      {isNational ? (
        <>Across all recorded meeting objections, the top concern is {nat}.</>
      ) : local ? (
        <>
          What residents{top?.jurisdiction_name ? ` of ${top.jurisdiction_name}` : ` in ${scopeLabel}`} raise most in
          their meetings: {local}. Items that touch it are listed first.
          {nat && <> Nationally: {nat}.</>}
        </>
      ) : (
        <>
          Not enough recorded objections in {scopeLabel} to rank by local concern, so items are listed by date.
          {nat && <> Nationally, the top concern is {nat}.</>}
        </>
      )}
    </p>
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
        {item.matches_local_concern && item.local_concern && (
          <span className="rounded bg-red-100 px-1.5 py-0.5 font-medium text-red-800">
            Matches local concern: {concernLabel(item.local_concern)}
          </span>
        )}
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
 * "Said in meetings" (#445): passages of meeting transcripts where a data center was
 * discussed, newest meeting first, grouped by meeting. Each passage quotes the transcript
 * with the matched words highlighted (server ts_headline -> highlightSnippet, React-escaped)
 * and links to that moment in the recording when the transcript is timed. Same ?state=&city=
 * scope as the rest of the page.
 */
function MeetingMentionsSection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'meeting-mentions', rawState ?? null, cityName ?? null],
    queryFn: () => fetchDataCenterMeetingMentions({ state: rawState, city: cityName }),
  })
  const items = data?.items ?? []
  // Group the passages under their meeting, keeping the API's newest-first order.
  const meetings: { videoId: string; passages: DataCenterMeetingMention[] }[] = []
  for (const item of items) {
    const last = meetings[meetings.length - 1]
    if (last && last.videoId === item.video_id) last.passages.push(item)
    else meetings.push({ videoId: item.video_id, passages: [item] })
  }
  const counts = data?.counts
  return (
    <section aria-labelledby="mentions-heading" className="mt-6">
      <h2 id="mentions-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Said in meetings
      </h2>
      <p className="mb-3 text-sm text-gray-600">
        Where data centers came up in recorded meetings in {scopeLabel}, quoted from the meeting transcript.
        {counts && counts.passages > 0 && (
          <>
            {' '}
            {counts.passages.toLocaleString()} passage{counts.passages === 1 ? '' : 's'} in{' '}
            {counts.meetings.toLocaleString()} meeting{counts.meetings === 1 ? '' : 's'}
            {items.length < counts.passages ? `; the newest ${items.length} are shown` : ''}.
          </>
        )}
      </p>
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading meeting transcripts for {scopeLabel}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load meeting transcripts.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : meetings.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No meeting transcripts mentioning a data center for {scopeLabel} yet.
        </div>
      ) : (
        <ul className="space-y-3">
          {meetings.map((m) => (
            <MeetingMentionCard key={m.videoId} passages={m.passages} />
          ))}
        </ul>
      )}
    </section>
  )
}

function formatMoment(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const mm = String(Math.floor((s % 3600) / 60)).padStart(h ? 2 : 1, '0')
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

function MeetingMentionCard({ passages }: { passages: DataCenterMeetingMention[] }) {
  const first = passages[0]
  const when = formatIsoDate(first.meeting_date)
  const where = [first.jurisdiction_name, first.state_code].filter(Boolean).join(', ')
  const site = passages.find((p) => p.site_name)?.site_name
  return (
    <li className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-gray-900">
          {first.meeting_title || 'Meeting'}
          {where && <span className="font-normal text-gray-600"> · {where}</span>}
        </p>
        <p className="text-sm text-gray-500">{when ?? 'Date not listed'}</p>
      </div>
      <ul className="mt-2 space-y-2">
        {passages.map((p) => (
          <li key={p.data_center_meeting_mention_id}>
            <blockquote className="line-clamp-4 border-l-4 border-primary-300 pl-3 text-sm text-gray-800">
              {highlightSnippet(p.evidence)}
            </blockquote>
            {p.jump_url && p.start_seconds != null && (
              <a
                href={p.jump_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-4 text-xs font-medium text-primary-700 hover:underline"
              >
                Watch at {formatMoment(p.start_seconds)}
              </a>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {site && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-700">Site: {site}</span>}
        <a href={first.video_url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary-700 hover:underline">
          Watch the meeting
        </a>
      </div>
    </li>
  )
}

/**
 * "Sites" (DC-4.1, #249; #958): data center sites from Epoch AI and the US Data Center Registry (both CC BY 4.0), with status and
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
        Data center sites from open inventories: Epoch AI (the largest AI sites) and the US Data Center Registry. Each
        site is credited to its own source. Sites a source stops listing stay here, marked, so they don&apos;t quietly
        disappear.
      </p>
      {cityName && (
        <p className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Sites are listed by state (Epoch AI gives no city), so these are all sites in {sitesScope}, not just {cityName}.
        </p>
      )}
      {counts && sites.length > 0 && (
        <p className="mb-3 text-xs text-gray-600">
          {counts.planned} planned · {counts.under_construction} under construction · {counts.operating} operating
          {(counts.cancelled ?? 0) > 0 && ` · ${counts.cancelled} cancelled (per the registry)`}
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
          {[...new Map(sites.map((s) => [s.source ?? 'epoch', s])).values()].map((s, i) => (
            <span key={s.source ?? 'epoch'}>
              {i > 0 && ' · '}
              Source: {s.attribution}
            </span>
          ))}
          . Each site links to its own record.
        </p>
      )}
    </section>
  )
}

function SiteCard({ site }: { site: DataCenterSite }) {
  const gone = site.status === 'no_longer_listed' || site.status === 'cancelled'
  const where = site.address ?? ([site.city, site.county && `${site.county} County`].filter(Boolean).join(', ') || null)
  const place = [where, site.state_code && !where?.includes(site.state_code) ? site.state_code : null]
    .filter(Boolean)
    .join(', ')
  return (
    <li className={`rounded-lg border bg-white p-4 shadow-sm ${gone ? 'border-dashed border-gray-300 opacity-90' : 'border-gray-200'}`}>
      <p className="font-semibold text-gray-900">{site.site_name}</p>
      {(site.owner || site.users || site.operator) && (
        <p className="text-sm text-gray-600">
          {[site.owner && `Owner: ${site.owner}`, site.users && `Used by: ${site.users}`, site.operator && `Operator: ${site.operator}`]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}
      {place && <p className="text-xs text-gray-500">{place}</p>}
      <p className={`mt-2 text-sm font-medium ${gone ? 'text-gray-600' : 'text-gray-900'}`}>
        {siteStatusLabel(site.status, site.last_known_status, site.last_seen_on)}
      </p>
      {site.construction_note && <p className="mt-1 text-xs italic text-gray-600">“{site.construction_note}”</p>}
      <p className="mt-2 text-xs text-gray-500">
        <a href={site.source_url} target="_blank" rel="noopener noreferrer" className="underline">
          {site.source_name}
        </a>
      </p>
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

/**
 * "Company meetings" (#532): town halls, open houses and information sessions a data center
 * company holds about its project, found in local news and the company's own press releases.
 * These are company-hosted, never government meetings, and each card says so. Every card
 * quotes each source with the meeting word highlighted (match-evidence rule) and names the
 * publisher. Recording candidates from a search are shown as unreviewed, never as the
 * recording. Same ?state=&city= scope as the rest of the page.
 */
function CommunityEventsSection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'community-events', rawState ?? null, cityName ?? null],
    queryFn: () => fetchCommunityEvents({ state: rawState, city: cityName }),
  })
  const events = data?.items ?? []
  return (
    <section aria-labelledby="community-events-heading" className="mt-6">
      <h2 id="community-events-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Company meetings <span className="font-normal text-gray-400">· {scopeLabel}</span>
      </h2>
      <p className="mb-3 text-sm text-gray-600">
        Town halls, open houses and information sessions held by data center companies, as local news and the
        companies&apos; own announcements report them. These are hosted by the company, not by a government.
        {data && data.unconfirmed > 0 && (
          <>
            {' '}
            {data.unconfirmed} more item{data.unconfirmed === 1 ? '' : 's'} mention a meeting but couldn&apos;t be
            matched to a company and project, so they aren&apos;t listed.
          </>
        )}
      </p>
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading company meetings for {scopeLabel}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load company meetings.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : events.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No company-hosted data center meetings found for {scopeLabel} yet.
        </div>
      ) : (
        <ul className="space-y-3">
          {events.map((e) => (
            <CommunityEventCard key={e.community_event_id} event={e} />
          ))}
        </ul>
      )}
    </section>
  )
}

function CommunityEventCard({ event }: { event: CommunityEvent }) {
  const sources = event.sources ?? []
  const candidates = event.recording_candidates ?? []
  const when = formatIsoDate(event.event_date)
  const where = [event.city, event.state_code].filter(Boolean).join(', ')
  return (
    <li className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-gray-900">
          {communityEventKindLabel(event.event_kind)}
          {event.project_name && <span className="font-normal text-gray-700"> · {event.project_name}</span>}
          {where && <span className="font-normal text-gray-600"> · {where}</span>}
        </p>
        <p className="text-sm text-gray-500">{when ?? 'Date not stated'}</p>
      </div>
      <p className="mt-1 text-xs">
        <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-900">
          Hosted by {event.host_name ?? 'the company'} · company meeting, not a government meeting
        </span>
      </p>
      <ul className="mt-2 space-y-2">
        {sources.map((s) => (
          <li key={s.url}>
            <blockquote className="line-clamp-4 border-l-4 border-primary-300 pl-3 text-sm text-gray-800">
              {highlightSnippet(s.evidence)}
            </blockquote>
            <p className="ml-4 text-xs text-gray-600">
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary-700 hover:underline">
                {s.publisher ?? 'Source'}
              </a>
              {s.source === 'company_feed' && ' (company press release)'}
              {s.published_on && ` · ${formatIsoDate(s.published_on)}`}
            </p>
          </li>
        ))}
      </ul>
      {event.recording_url ? (
        <a href={event.recording_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-xs font-medium text-primary-700 hover:underline">
          Recording (linked by the article)
        </a>
      ) : candidates.length > 0 ? (
        <div className="mt-2 text-xs text-gray-600">
          <p className="font-medium">Possible recordings, not yet reviewed:</p>
          <ul className="ml-4 list-disc">
            {candidates.map((r) => (
              <li key={r.video_url}>
                <a href={r.video_url} target="_blank" rel="noopener noreferrer" className="text-primary-700 hover:underline">
                  {r.title ?? r.video_url}
                </a>
                {r.channel && ` · ${r.channel}`}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-xs text-gray-500">No recording found.</p>
      )}
    </li>
  )
}

/**
 * "Projects" (#531/#532): announced and tracked data center projects with their companies,
 * every figure with its own source, and a timeline: announced → company meeting → planning →
 * council vote. Each timeline step says who held it (company or government) and where it
 * comes from. Figures the sources disagree on are listed per source, never merged.
 */
function ProjectsSection({ rawState, cityName, scopeLabel }: { rawState?: string; cityName?: string; scopeLabel: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['data-centers', 'projects', rawState ?? null, cityName ?? null],
    queryFn: () => fetchDataCenterProjects({ state: rawState, city: cityName, source: 'curated' }),
  })
  const projects = data?.items ?? []
  return (
    <section aria-labelledby="projects-heading" className="mt-6">
      <h2 id="projects-heading" className="mb-1 text-xl font-semibold text-gray-900">
        Projects <span className="font-normal text-gray-400">· {scopeLabel}</span>
      </h2>
      <p className="mb-3 text-sm text-gray-600">
        Data center projects named in company announcements and news, with who is building them and each figure
        quoted from its source. Tracked Epoch AI sites are listed under Sites.
      </p>
      {isLoading ? (
        <div role="status" className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading projects for {scopeLabel}…
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load projects.{' '}
          <button type="button" onClick={() => refetch()} className="font-medium underline">
            Retry
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No announced data center projects found for {scopeLabel} yet.
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {projects.map((p) => (
            <ProjectCard key={p.project_id} project={p} />
          ))}
        </ul>
      )}
    </section>
  )
}

function ProjectCard({ project }: { project: DataCenterProject }) {
  const companies = project.companies ?? []
  const figures = project.figures ?? []
  const timeline = project.timeline ?? []
  const place = [project.city, project.county, project.state].filter(Boolean).join(', ') || project.area
  return (
    <li className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="font-semibold text-gray-900">{project.project_name}</p>
      {place && <p className="text-xs text-gray-500">{place}</p>}
      {companies.length > 0 && (
        <p className="mt-1 text-sm text-gray-700">
          {companies.map((c) => `${c.company_name ?? 'Company'} (${c.role})`).join(' · ')}
        </p>
      )}
      <blockquote className="mt-2 border-l-4 border-gray-200 pl-3 text-xs italic text-gray-700">
        “{project.source_excerpt}”{' '}
        <a href={project.source_url} target="_blank" rel="noopener noreferrer" className="not-italic text-primary-700 hover:underline">
          source
        </a>
      </blockquote>
      {figures.length > 0 && (
        <div className="mt-2 text-xs text-gray-700">
          <p className="font-medium">
            Figures{project.has_conflicting_figures && <span className="text-amber-700"> (sources disagree; each shown)</span>}
          </p>
          <ul className="ml-4 list-disc">
            {figures.map((f) => (
              <li key={`${f.metric}-${f.source_url}-${f.value}`}>
                {figureLabel(f.metric, f.value, f.unit)}: “{f.source_excerpt}”{' '}
                <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="text-primary-700 hover:underline">
                  source
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
      {timeline.length > 0 && (
        <ol className="mt-3 space-y-2 border-l border-gray-200 pl-3 text-xs">
          {timeline.map((t, i) => (
            <li key={`${t.stage}-${i}`}>
              <p className="font-medium text-gray-900">
                {timelineStageLabel(t.stage)} · {formatIsoDate(t.on) ?? 'Date not stated'}
              </p>
              <p className="text-gray-700">{t.label}</p>
              <p className="text-gray-500">
                Held by {t.host} · Source:{' '}
                {t.url ? (
                  t.url.startsWith('/') ? (
                    <Link to={t.url} className="text-primary-700 hover:underline">{t.source_label}</Link>
                  ) : (
                    <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-primary-700 hover:underline">
                      {t.source_label}
                    </a>
                  )
                ) : (
                  t.source_label
                )}
              </p>
              {t.evidence && <p className="line-clamp-3 text-gray-700">{highlightSnippet(t.evidence)}</p>}
            </li>
          ))}
        </ol>
      )}
    </li>
  )
}
