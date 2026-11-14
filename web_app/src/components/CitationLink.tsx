import { Link } from 'react-router-dom'
import { PlayIcon } from '@heroicons/react/24/outline'
import { formatTimestamp, meetingMomentPath } from '../lib/timestamp'

/**
 * Who said it, when, and a link to that moment in the recording (CORE-2.1, #240).
 *
 * Only real values are shown: a missing speaker reads "Speaker not identified" and a missing time "time not
 * recorded" (the link then opens the meeting at the start). Nothing is guessed.
 */
export interface CitationLinkProps {
  meetingId: string
  startSeconds: number | null
  speakerName?: string | null
  speakerRole?: string | null
  /** ISO date of the meeting (YYYY-MM-DD). */
  meetingDate?: string | null
}

function displayDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function CitationLink({
  meetingId,
  startSeconds,
  speakerName,
  speakerRole,
  meetingDate,
}: CitationLinkProps) {
  const who = speakerName ? (speakerRole ? `${speakerName}, ${speakerRole}` : speakerName) : 'Speaker not identified'
  const hasTime = startSeconds != null && startSeconds >= 0
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-600">
      <span>
        Said by <span className="font-medium text-gray-900">{who}</span>
      </span>
      {meetingDate && (
        <>
          <span aria-hidden="true">·</span>
          <span>{displayDate(meetingDate)}</span>
        </>
      )}
      <span aria-hidden="true">·</span>
      <Link
        to={meetingMomentPath(meetingId, hasTime ? startSeconds : null)}
        className="inline-flex items-center gap-1 rounded bg-teal-50 px-1.5 py-0.5 font-mono text-xs tabular-nums text-teal-800 ring-1 ring-inset ring-teal-200 hover:bg-teal-100"
        title={hasTime ? 'Hear it in the recording' : 'Open the meeting'}
      >
        <PlayIcon className="h-3 w-3" aria-hidden="true" />
        {hasTime ? formatTimestamp(startSeconds) : 'time not recorded'}
      </Link>
    </span>
  )
}
