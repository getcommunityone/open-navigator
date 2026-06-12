import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchPolicyQuestions, type PolicyQuestionSummary } from '../api/policyQuestions'

export default function PolicyQuestionsPage() {
  const { data, isLoading } = useQuery<PolicyQuestionSummary[]>({
    queryKey: ['policy-questions'],
    queryFn: () => fetchPolicyQuestions({ limit: 100 }),
  })

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-4">
        <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">
          Policy question registry
        </p>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Questions that keep coming up</h1>
        <p className="text-gray-500 mb-6 text-sm">
          Recurring choices that local governments (and, soon, state legislatures) face — with how
          they usually go and the arguments on each side.
        </p>

        {isLoading ? (
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        ) : (
          <div className="space-y-2">
            {(data || []).map((q) => {
              const pct =
                q.jurisdictions_total > 0
                  ? Math.round((q.jurisdictions_approved / q.jurisdictions_total) * 100)
                  : 0
              return (
                <Link
                  key={q.question_id}
                  to={`/policy-question/${q.question_id}`}
                  className={`block rounded-lg border bg-white p-4 hover:shadow-sm transition ${
                    q.is_featured
                      ? 'border-indigo-200 ring-1 ring-indigo-100 hover:border-indigo-300'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-gray-900">
                      {q.is_featured && (
                        <span className="mr-2 inline-block rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-600 align-middle">
                          📌 Featured
                        </span>
                      )}
                      {q.canonical_text}
                    </span>
                    {q.jurisdictions_total > 0 && (
                      <span className="shrink-0 text-sm text-gray-500">
                        {q.jurisdictions_approved}/{q.jurisdictions_total} approved ({pct}%)
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-400">
                    {q.primary_theme && q.primary_theme !== '__unthemed__' && (
                      <span>{q.primary_theme}</span>
                    )}
                    <span>· {q.instances_total} instances</span>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
