import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { highlightSnippet } from '../lib/highlight'

/**
 * Jev's reading of meetings for one policy question (#1032): how many meetings the classifier read as debating it,
 * what it read happened (approved, denied, tabled, moratorium, discussed only), and the meetings with the verbatim
 * passage that put them in the record. Labelled as a classifier's reading, apart from analyzed decisions. Shows
 * nothing when the question has no Jev reading.
 */
interface JevItem {
  video_id: string
  meeting_title: string | null
  meeting_date: string | null
  jurisdiction_name: string | null
  state_code: string | null
  outcome: string | null
  outcome_p: number | null
  evidence: string | null
  jump_url: string | null
}
interface JevOut {
  available: boolean
  meetings: number
  debated: number
  outcomes: Record<string, number>
  items: JevItem[]
}

const LABEL: Record<string, string> = {
  approved: 'approved',
  denied: 'denied',
  tabled_or_deferred: 'tabled or deferred',
  moratorium: 'moratorium',
  discussed_no_action: 'discussed, no action',
}
const ORDER = ['approved', 'denied', 'tabled_or_deferred', 'moratorium', 'discussed_no_action']
const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function JevQuestionReading({ questionId, stateCode, city }: { questionId: string; stateCode?: string | null; city?: string | null }) {
  const [open, setOpen] = useState(false)
  const [outcome, setOutcome] = useState<string | null>(null)
  const params = { ...(stateCode ? { state: stateCode } : {}), ...(city ? { city } : {}), ...(outcome ? { outcome } : {}), limit: 10 }
  const q = useQuery({
    queryKey: ['policy-question', questionId, 'jev', stateCode ?? '', city ?? '', outcome ?? ''],
    queryFn: async () => (await api.get<JevOut>(`/policy-question/${encodeURIComponent(questionId)}/jev`, { params })).data,
    staleTime: 5 * 60_000,
  })
  const d = q.data
  if (!d || !d.available || d.meetings === 0) return null
  const actions = ORDER.filter((k) => (d.outcomes[k] ?? 0) > 0)
  return (
    <div className="mt-3 rounded-lg border border-teal-100 bg-teal-50/50 px-3 py-2.5 text-sm">
      <p className="text-gray-800">
        <span className="font-semibold">Meetings screened by Jev:</span> {d.meetings.toLocaleString()} read as taking up this question
        {actions.length > 0 && (
          <>
            {' · '}
            {actions.map((k, i) => (
              <span key={k}>
                {i > 0 && ', '}
                <button
                  type="button"
                  onClick={() => {
                    setOutcome(outcome === k ? null : k)
                    setOpen(true)
                  }}
                  className={`underline-offset-2 hover:underline ${outcome === k ? 'font-semibold text-teal-800' : 'text-teal-700'}`}
                  aria-pressed={outcome === k}
                >
                  {d.outcomes[k]!.toLocaleString()} {LABEL[k]}
                </button>
              </span>
            ))}
          </>
        )}
      </p>
      <p className="mt-0.5 text-xs text-gray-500">
        Jev is a classifier: it read each transcript and judged what happened. These are readings, not the decisions analyzed above.
      </p>
      <button type="button" onClick={() => setOpen((v) => !v)} className="mt-1 text-xs font-semibold text-teal-700" aria-expanded={open}>
        {open ? 'Hide meetings' : 'Show meetings'}
      </button>
      {open && (
        <ul className="mt-2 space-y-2">
          {d.items.map((m) => (
            <li key={m.video_id} className="rounded-md border border-gray-100 bg-white px-3 py-2">
              <p className="text-xs text-gray-500">
                {[m.jurisdiction_name, m.state_code].filter(Boolean).join(', ')}
                {fmtDate(m.meeting_date) ? ` · ${fmtDate(m.meeting_date)}` : ''}
                {m.outcome ? <> · <span className="font-semibold text-gray-700">{LABEL[m.outcome] ?? m.outcome}</span></> : null}
              </p>
              {m.meeting_title && <p className="text-sm font-medium text-gray-900">{m.meeting_title}</p>}
              {m.evidence && <p className="mt-1 text-sm italic text-gray-700">“{highlightSnippet(m.evidence)}”</p>}
              {m.jump_url && (
                <a href={m.jump_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-xs font-semibold text-teal-700">
                  Hear it ↗
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
