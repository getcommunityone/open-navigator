import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterCommentMetrics, type DataCenterCommentMetrics } from '../../api/dataCenters'
import { storyScopeLabel, type StoryScope } from '../../utils/dataStory'
import { fmt } from '../../utils/stanceGame'

interface Props {
  scope: StoryScope
  /** Meeting year the line counts (the story's year). */
  year?: number
}

const pct = (share: number | null | undefined) => (share == null ? null : `${Math.round(share * 100)}%`)

/** "1,234 public comments at 210 local governments in 2026" — null when the numbers aren't there (never 0 for unknown). */
export function commentMetricsLine(m: DataCenterCommentMetrics | undefined, scope: StoryScope, year: number): string | null {
  if (!m || m.comments <= 0) return null
  const place = scope.stateName ? ` in ${storyScopeLabel(scope)}` : ''
  const govs = m.governments === 1 ? '1 local government' : `${fmt(m.governments)} local governments`
  const comments = m.comments === 1 ? '1 public comment' : `${fmt(m.comments)} public comments`
  return `${comments} at ${govs}${place} in ${year}`
}

/**
 * Comment-level counts from our own captions (#1233), added under the hand-counted "Who spoke up" figures: how many public
 * comments about a data center the caption segmenter found, at how many local governments, the companies they name and how
 * many mention AI. Stance is not shown here (it needs the per-comment classifier, on hold). Scope follows ?state=&city=.
 * Missing or failed data shows one quiet line, never a stand-in number.
 */
export default function CommentMetricsBlock({ scope, year = 2026 }: Props) {
  const q = useQuery<DataCenterCommentMetrics>({
    queryKey: ['dc-comment-metrics', year, scope.stateCode ?? 'national', scope.city ?? ''],
    queryFn: () =>
      fetchDataCenterCommentMetrics({ year, state: scope.stateCode, city: scope.city ?? undefined }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  if (q.isLoading) return null
  const line = commentMetricsLine(q.data, scope, year)
  if (q.isError || !q.data || !line) {
    return (
      <p className="stance-note" data-testid="comment-metrics-off">
        Comment-level counts from meeting captions aren&apos;t available for this scope yet.
      </p>
    )
  }
  const m = q.data
  const companies = m.companies.slice(0, 5)
  const ai = m.ai_mentions
  return (
    <div className="stance-voices-comments" data-testid="comment-metrics">
      <p className="stance-note">
        The figures above are hand-counted from meeting analyses. From our own meeting captions:{' '}
        <strong>{line}</strong>.
      </p>
      {(companies.length > 0 || ai) && (
        <dl className="stance-voices-figures">
          {ai && (
            <div data-figure="ai">
              <dt>Mention AI</dt>
              <dd>
                {fmt(ai.count)}
                {pct(ai.share) ? ` (${pct(ai.share)})` : ''}
              </dd>
            </div>
          )}
          {companies.map((c) => (
            <div key={c.key} data-figure={`company-${c.key}`}>
              <dt>Name {c.label}</dt>
              <dd>{fmt(c.count)}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="stance-note">
        A comment is one speaker&apos;s turn at the microphone, found by self-introductions and the chair calling speakers;
        companies and AI are keyword matches. Whether each comment is for or against isn&apos;t counted yet.
      </p>
    </div>
  )
}
