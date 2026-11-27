import { useQuery } from '@tanstack/react-query'
import { fetchRecordedCoverage } from '../../api/sitesTimeline'
import { coverageText, type CoverageScope } from '../../utils/coverageLine'
import './CoverageLine.css'

/**
 * The recording-coverage line (#1348), under a story's basis line on the Overview and the home hero: "From recordings of 29
 * Florida local governments (1,035 meetings). Many Florida governments aren't in our recordings yet." It reads the same scope
 * as the counts above it (label and data move together) and renders nothing until the real counts are in. Phones show the
 * short form.
 */
export default function CoverageLine({ scope, className = '' }: { scope: CoverageScope; className?: string }) {
  const city = scope.stateCode ? scope.city : null
  const q = useQuery({
    queryKey: ['coverage', 'recorded-meetings', scope.stateCode ?? '', city ?? ''],
    queryFn: () => fetchRecordedCoverage(scope.stateCode, city),
    staleTime: 30 * 60_000,
    retry: 1,
  })
  const text = coverageText(q.data, scope)
  if (!text) return null
  return (
    <p className={`coverage-line ${className}`.trim()} data-testid="coverage-line">
      <span className="coverage-line-full">{text.full}</span>
      <span className="coverage-line-short" aria-hidden="true">
        {text.short}
      </span>
    </p>
  )
}
