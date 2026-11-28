import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PlayCircleIcon } from '@heroicons/react/24/outline'
import api from '../lib/api'
import { withSpan } from '../instrumentation'
import PageClose from '../components/PageClose'
import { useDocumentTitle } from '../utils/useDocumentTitle'
import {
  formatDay,
  groupMembers,
  howHeard,
  meetingCountLabel,
  memberCountLabel,
  roleLabel,
  type BodyDetailResponse,
} from '../lib/governingBodies'

/**
 * One governing body (#1446): its members and roles, officials heard recently, and its recent meetings.
 * Route: /bodies/:bodyId. The scope label under the title names the place the body belongs to (the body is the
 * filter), and links back to that place's page. Every figure comes from GET /api/bodies/{id}.
 */
export default function BodyDetail() {
  const { bodyId = '' } = useParams<{ bodyId: string }>()
  const { data, isLoading, isError } = useQuery<BodyDetailResponse>({
    queryKey: ['body-detail', bodyId],
    queryFn: () =>
      withSpan(
        'body_detail.load',
        async () => (await api.get<BodyDetailResponse>(`/bodies/${encodeURIComponent(bodyId)}`, { params: { limit: 50 } })).data,
        { 'body.id': bodyId },
      ),
    enabled: Boolean(bodyId),
  })
  const b = data?.body
  useDocumentTitle(b ? `${b.body_name} · ${b.jurisdiction_name}` : 'Governing body')
  const seats = groupMembers(data?.members ?? [])
  const current = seats.filter((s) => s.is_current)
  const past = seats.filter((s) => !s.is_current)
  const placeId = b?.jurisdiction_id.match(/_(\d+)$/)?.[1] ?? b?.jurisdiction_id

  return (
    <div className="min-h-screen page-bg">
      <PageClose />
      <div className="mx-auto max-w-5xl px-4 pb-10 sm:px-6">
        {isLoading && <p className="text-gray-600">Loading…</p>}
        {isError && (
          <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">This body could not be loaded.</p>
        )}
        {b && (
          <>
            <header className="mb-6">
              <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">{b.body_name}</h1>
              <p className="mt-1 text-sm font-medium text-gray-700" data-testid="body-scope">
                <Link to={`/jurisdiction/${encodeURIComponent(placeId ?? '')}/meetings`} className="underline">
                  {b.jurisdiction_name}
                  {b.state_code ? `, ${b.state_code}` : ''}
                </Link>
              </p>
              <p className="mt-2 text-sm text-gray-600">
                {meetingCountLabel(b.meeting_count)}
                {b.first_meeting_date && b.last_meeting_date
                  ? ` (${formatDay(b.first_meeting_date)} to ${formatDay(b.last_meeting_date)})`
                  : ''}{' '}
                · {memberCountLabel(b.member_count)}
              </p>
            </header>

            <section aria-labelledby="members-heading" className="mb-8">
              <h2 id="members-heading" className="text-xl font-bold text-gray-900">
                Members and roles
              </h2>
              {current.length === 0 ? (
                <p className="mt-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
                  Members of the {b.body_name} are not on file yet.
                </p>
              ) : (
                <ul className="mt-3 divide-y divide-gray-100 overflow-hidden rounded-lg border border-gray-200 bg-white">
                  {current.map((s) => (
                    <li key={s.key} className="p-3">
                      <span className="block font-semibold text-gray-900">
                        {s.person_id ? (
                          <Link to={`/person/${encodeURIComponent(s.person_id)}`} className="hover:underline">
                            {s.member_name}
                          </Link>
                        ) : (
                          s.member_name
                        )}
                      </span>
                      <span className="block text-sm text-gray-600">{s.lines.join('; ')}</span>
                    </li>
                  ))}
                </ul>
              )}
              {past.length > 0 && (
                <div className="mt-3 text-sm text-gray-600">
                  <p className="font-semibold text-gray-700">Seats that ended in the last year</p>
                  <ul className="mt-1 list-disc pl-5">
                    {past.map((s) => (
                      <li key={s.key}>
                        {s.member_name}, {s.lines.join('; ')}
                        {s.end_date ? ` (ended ${formatDay(s.end_date)})` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section aria-labelledby="heard-heading" className="mb-8">
              <h2 id="heard-heading" className="text-xl font-bold text-gray-900">
                Officials heard most recently
              </h2>
              {(data?.recent_speakers.length ?? 0) === 0 ? (
                <p className="mt-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
                  No roster members matched in this body’s recent recordings.
                </p>
              ) : (
                <ul className="mt-3 divide-y divide-gray-100 overflow-hidden rounded-lg border border-gray-200 bg-white">
                  {data!.recent_speakers.map((h) => (
                    <li key={h.person_id ?? h.member_name} className="flex items-center gap-3 p-3">
                      <span className="min-w-0 flex-1">
                        <span className="block font-semibold text-gray-900">{h.member_name}</span>
                        <span className="block text-xs text-gray-500">
                          {roleLabel(h.role)} · last {howHeard(h.attribution_method)} {formatDay(h.last_heard_date)} ·{' '}
                          {h.meetings_heard} meeting{h.meetings_heard === 1 ? '' : 's'}
                        </span>
                      </span>
                      {h.moment_url && (
                        <a
                          href={h.moment_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Play ${h.member_name} at that moment (opens YouTube)`}
                          className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full text-teal-800 hover:bg-teal-50"
                        >
                          <PlayCircleIcon aria-hidden="true" className="h-6 w-6" />
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-labelledby="meetings-heading">
              <h2 id="meetings-heading" className="text-xl font-bold text-gray-900">
                Recent meetings
              </h2>
              {(data?.meetings.length ?? 0) === 0 ? (
                <p className="mt-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
                  No meetings of this body on file yet.
                </p>
              ) : (
                <ul className="mt-3 divide-y divide-gray-100 overflow-hidden rounded-lg border border-gray-200 bg-white">
                  {data!.meetings.map((mt) => (
                    <li key={mt.meeting_body_id} className="flex flex-wrap items-baseline gap-x-3 p-3">
                      <span className="w-28 flex-none text-sm text-gray-500">{formatDay(mt.meeting_date)}</span>
                      <span className="min-w-0 flex-1 text-sm text-gray-900">
                        {mt.event_meeting_id ? (
                          <Link to={`/meetings/${mt.event_meeting_id}`} className="hover:underline">
                            {mt.meeting_title || b.body_name}
                          </Link>
                        ) : mt.video_url ? (
                          <a href={mt.video_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                            {mt.meeting_title || b.body_name}
                          </a>
                        ) : (
                          mt.meeting_title || b.body_name
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}
