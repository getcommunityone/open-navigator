import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  fetchPolicyQuestion,
  type CanonicalArgument,
  type PolicyQuestionDetail,
} from '../api/policyQuestions'

const OUTCOME_COLORS: Record<string, string> = {
  approved: 'bg-green-500',
  denied: 'bg-red-500',
  deferred: 'bg-amber-500',
  other: 'bg-gray-400',
}

function RollupBar({ q }: { q: PolicyQuestionDetail }) {
  const r = q.rollup
  const total = r.approved_count + r.denied_count + r.deferred_count + r.other_count
  const seg = (n: number) => (total > 0 ? `${(n / total) * 100}%` : '0%')
  const pct =
    r.jurisdictions_total > 0
      ? Math.round((r.jurisdictions_approved / r.jurisdictions_total) * 100)
      : 0
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      {r.instances_total === 0 ? (
        <p className="text-gray-500">No mapped instances yet.</p>
      ) : (
        <>
          <p className="text-lg font-semibold text-gray-900">
            {r.jurisdictions_approved} of {r.jurisdictions_total} jurisdictions approved
            <span className="text-gray-500 font-normal"> ({pct}%)</span>
          </p>
          <p className="text-sm text-gray-500 mb-3">
            {r.decisions_total} local decision{r.decisions_total === 1 ? '' : 's'}
            {r.bills_total > 0 ? ` · ${r.bills_total} state bills` : ''} ·{' '}
            {r.states_total} state{r.states_total === 1 ? '' : 's'}
          </p>
          <div className="flex h-3 w-full overflow-hidden rounded-full">
            {(['approved', 'denied', 'deferred', 'other'] as const).map((k) => {
              const n = r[`${k}_count` as keyof typeof r] as number
              return n > 0 ? (
                <div
                  key={k}
                  className={OUTCOME_COLORS[k]}
                  style={{ width: seg(n) }}
                  title={`${k}: ${n}`}
                />
              ) : null
            })}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            <span>● approved {r.approved_count}</span>
            <span>● denied {r.denied_count}</span>
            <span>● deferred {r.deferred_count}</span>
            <span>● other {r.other_count}</span>
          </div>
        </>
      )}
    </div>
  )
}

function ArgumentCard({ a }: { a: CanonicalArgument }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-gray-900 text-sm">{a.label}</span>
        <span className="shrink-0 text-[11px] text-gray-400">×{a.member_count}</span>
      </div>
      {a.summary && <p className="mt-1 text-sm text-gray-600">{a.summary}</p>}
      <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
        {a.frame_label && (
          <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-indigo-700">
            {a.frame_label}
          </span>
        )}
        {a.source_role && (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">{a.source_role}</span>
        )}
      </div>
    </div>
  )
}

export default function PolicyQuestionPage() {
  const { questionId } = useParams<{ questionId: string }>()
  const { data: q, isLoading, error } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question', questionId],
    queryFn: () => fetchPolicyQuestion(questionId as string),
    enabled: !!questionId,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </div>
    )
  }
  if (error || !q) {
    return (
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <p className="text-red-700">Unable to load this policy question.</p>
          <Link to="/policy-questions" className="text-blue-600 underline">
            Back to policy questions
          </Link>
        </div>
      </div>
    )
  }

  const pros = q.arguments.filter((a) => a.stance === 'pro')
  const cons = q.arguments.filter((a) => a.stance === 'con')
  const other = q.arguments.filter((a) => a.stance !== 'pro' && a.stance !== 'con')

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-4 space-y-6">
        <div>
          <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">
            This question keeps coming up
          </p>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">{q.canonical_text}</h1>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
            {q.primary_theme && q.primary_theme !== '__unthemed__' && (
              <span className="rounded bg-gray-100 px-2 py-0.5">{q.primary_theme}</span>
            )}
            {q.scope && <span className="rounded bg-gray-100 px-2 py-0.5">scope: {q.scope}</span>}
            {q.topic_code && (
              <span className="rounded bg-gray-100 px-2 py-0.5">CAP {q.topic_code}</span>
            )}
          </div>
        </div>

        <RollupBar q={q} />

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-green-700">
              Arguments for ({pros.length})
            </h2>
            <div className="space-y-2">
              {pros.length ? pros.map((a) => <ArgumentCard key={a.argument_id} a={a} />) : (
                <p className="text-sm text-gray-400">None extracted.</p>
              )}
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold text-red-700">
              Arguments against ({cons.length})
            </h2>
            <div className="space-y-2">
              {cons.length ? cons.map((a) => <ArgumentCard key={a.argument_id} a={a} />) : (
                <p className="text-sm text-gray-400">None extracted.</p>
              )}
            </div>
          </div>
        </div>
        {other.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-gray-600">Other arguments</h2>
            {other.map((a) => <ArgumentCard key={a.argument_id} a={a} />)}
          </div>
        )}

        <div>
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Where it came up ({q.rollup.instances_total})
          </h2>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-100">
                {q.sample_instances.map((i) => (
                  <tr key={i.instance_id}>
                    <td className="px-3 py-2">
                      {i.source_type === 'state_bill' ? (
                        <Link to={`/bills/${i.source_id}`} className="text-blue-600 hover:underline">
                          {i.jurisdiction_name || i.state_code} (bill)
                        </Link>
                      ) : (
                        <Link
                          to={`/decisions/${i.source_id}`}
                          className="text-blue-600 hover:underline"
                        >
                          {i.jurisdiction_name || i.city || i.state_code}
                        </Link>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-600">{i.outcome_raw}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs text-white ${
                          OUTCOME_COLORS[i.outcome_normalized || 'other']
                        }`}
                      >
                        {i.outcome_normalized}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
