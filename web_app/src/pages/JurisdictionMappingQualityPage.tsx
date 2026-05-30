import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import EntityQualityDashboard, {
  type QualityPayload,
} from './jurisdiction-quality/EntityQualityDashboard'

async function fetchPayload(): Promise<QualityPayload> {
  const res = await fetch('/data/jurisdiction_mapping_quality.json', { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as QualityPayload
}

export default function JurisdictionMappingQualityPage() {
  const [refreshOpen, setRefreshOpen] = useState(false)
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['jurisdiction-mapping-quality-json'],
    queryFn: fetchPayload,
    staleTime: 60_000,
  })

  useEffect(() => {
    const id = 'open-navigator-jmq-ibm-plex'
    if (document.getElementById(id)) return
    const link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    link.href =
      'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap'
    document.head.appendChild(link)
  }, [])

  return (
    <div className="jmq-quality-page min-h-screen w-full">
      {isPending && (
        <div className="jmq-main">
          <div className="jmq-card p-8 text-center font-mono text-sm text-[var(--jmq-text-muted)]">Loading snapshot…</div>
        </div>
      )}

      {isError && (
        <div className="jmq-main">
          <div className="jmq-card border-[var(--jmq-red)] p-0 overflow-hidden">
            <div className="border-b border-[var(--jmq-border)] bg-[var(--jmq-red-dim)] px-4 py-3">
              <h2 className="text-sm font-bold text-[var(--jmq-red)]">Could not load snapshot</h2>
            </div>
            <div className="p-4">
              <p className="font-mono text-sm">
                <code>/data/jurisdiction_mapping_quality.json</code>: {(error as Error)?.message ?? 'unknown error'}
              </p>
            </div>
          </div>
        </div>
      )}

      {data && !data.summary_by_type?.length && (
        <div className="jmq-main">
          <div className="jmq-card text-sm text-[var(--jmq-text-muted)]">
            No summary rows yet — run dbt and{' '}
            <code>export_jurisdiction_mapping_quality_json.py</code>, then refresh.
          </div>
        </div>
      )}

      {data && data.summary_by_type && data.summary_by_type.length > 0 ? (
        <EntityQualityDashboard data={data} refreshOpen={refreshOpen} setRefreshOpen={setRefreshOpen} />
      ) : null}
    </div>
  )
}
