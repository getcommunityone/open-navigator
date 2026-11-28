import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BuildingLibraryIcon, ChevronRightIcon, PlayCircleIcon } from '@heroicons/react/24/outline'
import {
  formatDay,
  howHeard,
  listedBodies,
  meetingCountLabel,
  memberCountLabel,
  officialsHeard,
  roleLabel,
  type JurisdictionBodies,
} from '../../lib/governingBodies'

const FIRST = 6

/**
 * "Who governs <place>" (#1446): the place's bodies with meetings and members on file, each opening its body page.
 * The heading names the place the data is for (scope label = the jurisdiction in the URL). Counts come from the API;
 * a body with no members on file says so rather than showing a number.
 */
export function WhoGoverns({ data }: { data: JurisdictionBodies }) {
  const [showAll, setShowAll] = useState(false)
  const bodies = listedBodies(data.bodies)
  const shown = showAll ? bodies : bodies.slice(0, FIRST)
  return (
    <section aria-labelledby="who-governs-heading" className="mb-8" data-testid="who-governs">
      <h2 id="who-governs-heading" className="text-xl font-bold text-gray-900">
        Who governs {data.jurisdiction_name}
      </h2>
      <p className="mt-1 text-sm text-gray-600">
        Bodies named by the meetings we hold and by official rosters. Meetings on file count distinct meeting dates.
      </p>
      {bodies.length === 0 ? (
        <p className="mt-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
          No governing bodies on file for {data.jurisdiction_name} yet.
        </p>
      ) : (
        <ul className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {shown.map((b) => (
            <li key={b.governing_body_id}>
              <Link
                to={`/bodies/${encodeURIComponent(b.governing_body_id)}`}
                className="flex min-h-[44px] items-start gap-3 rounded-lg border border-gray-200 bg-white p-4 hover:border-teal-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-700"
              >
                <BuildingLibraryIcon aria-hidden="true" className="mt-0.5 h-5 w-5 flex-none text-teal-700" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-gray-900">{b.body_name}</span>
                  <span className="mt-0.5 block text-sm text-gray-600">
                    {meetingCountLabel(b.meeting_count)} · {memberCountLabel(b.member_count)}
                  </span>
                  {b.is_primary && b.members.some((m) => m.is_current) && (
                    <span className="mt-1 block truncate text-xs text-gray-500">
                      {b.members
                        .filter((m) => m.is_current)
                        .slice(0, 3)
                        .map((m) => `${m.member_name} (${roleLabel(m.role, m.role_title)})`)
                        .join(', ')}
                      {b.member_count > 3 ? ' …' : ''}
                    </span>
                  )}
                </span>
                <ChevronRightIcon aria-hidden="true" className="mt-0.5 h-5 w-5 flex-none text-gray-400" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {bodies.length > FIRST && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 min-h-[44px] text-sm font-semibold text-teal-800 underline"
        >
          {showAll ? 'Show fewer bodies' : `Show all ${bodies.length} bodies`}
        </button>
      )}
    </section>
  )
}

/**
 * "Officials heard most recently" (#1446): roster members the chair called on or who answered the roll call in the
 * place's recent meetings, each with a play link to that moment. Residents are never listed (the API holds roster
 * members only).
 */
export function OfficialsHeard({ data }: { data: JurisdictionBodies }) {
  const heard = officialsHeard(data.bodies)
  return (
    <section aria-labelledby="officials-heard-heading" className="mb-8" data-testid="officials-heard">
      <h2 id="officials-heard-heading" className="text-xl font-bold text-gray-900">
        Officials heard most recently
      </h2>
      <p className="mt-1 text-sm text-gray-600">
        {data.jurisdiction_name} officials on a roster whom the chair called on, or who answered the roll call, in the
        last 18 months of recorded meetings.
      </p>
      {heard.length === 0 ? (
        <p className="mt-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
          No officials matched in recent recordings for {data.jurisdiction_name} yet.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-gray-100 overflow-hidden rounded-lg border border-gray-200 bg-white">
          {heard.map((h) => (
            <li key={h.person_id ?? h.member_name} className="flex items-center gap-3 p-3">
              <span className="min-w-0 flex-1">
                <span className="block font-semibold text-gray-900">
                  {h.person_id ? (
                    <Link to={`/person/${encodeURIComponent(h.person_id)}`} className="hover:underline">
                      {h.member_name}
                    </Link>
                  ) : (
                    h.member_name
                  )}
                </span>
                <span className="block text-sm text-gray-600">
                  {roleLabel(h.role)} · {h.body_name}
                </span>
                <span className="block text-xs text-gray-500">
                  Last {howHeard(h.attribution_method)} {formatDay(h.last_heard_date)} · {h.meetings_heard} meeting
                  {h.meetings_heard === 1 ? '' : 's'}
                </span>
              </span>
              {h.moment_url && (
                <a
                  href={h.moment_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Play ${h.member_name} at that moment (opens YouTube)`}
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 rounded-full px-3 text-sm font-semibold text-teal-800 hover:bg-teal-50"
                >
                  <PlayCircleIcon aria-hidden="true" className="h-6 w-6" />
                  <span className="hidden sm:inline">Play</span>
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
