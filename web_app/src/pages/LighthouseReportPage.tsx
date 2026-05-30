import { useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const DEFAULT_WEBSITE_URL = 'https://www.communityone.com/'

type LighthouseScores = {
  performance: number | null
  accessibility: number | null
  best_practices: number | null
  seo: number | null
}

export type LighthouseReportPayload = {
  scan_key: string
  batch_id: string
  jurisdiction_id: string
  website_url: string
  final_url: string | null
  scanned_at: string | null
  status: string
  lighthouse_version: string | null
  requested_url: string | null
  scores: LighthouseScores
  run_warnings: string[]
  screenshot_data_url: string | null
}

function scoreStroke(score: number | null): string {
  if (score == null) return '#94a3b8'
  if (score >= 90) return '#15803d'
  if (score >= 50) return '#ca8a04'
  return '#b91c1c'
}

function LighthouseGauge({
  label,
  score,
  size = 'sm',
}: {
  label: string
  score: number | null
  size?: 'sm' | 'lg'
}) {
  const r = size === 'lg' ? 54 : 38
  const c = 2 * Math.PI * r
  const pct = score == null ? 0 : Math.min(100, Math.max(0, score)) / 100
  const offset = c * (1 - pct)
  const stroke = scoreStroke(score)
  const dim = size === 'lg' ? 136 : 100
  const view = dim
  const cx = view / 2
  const cy = view / 2

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="relative"
        style={{ width: dim, height: dim }}
        aria-label={`${label} score ${score == null ? 'not available' : score}`}
      >
        <svg width={dim} height={dim} viewBox={`0 0 ${view} ${view}`} className="block -rotate-90">
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="#e2e8f0"
            strokeWidth={size === 'lg' ? 10 : 8}
          />
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={stroke}
            strokeWidth={size === 'lg' ? 10 : 8}
            strokeLinecap="round"
            strokeDasharray={`${c} ${c}`}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className={
              size === 'lg'
                ? 'text-3xl font-semibold tabular-nums text-slate-900'
                : 'text-xl font-semibold tabular-nums text-slate-900'
            }
          >
            {score == null ? '—' : score}
          </span>
        </div>
      </div>
      <span
        className={
          size === 'lg'
            ? 'text-center text-base font-medium text-slate-800'
            : 'text-center text-sm font-medium text-slate-700'
        }
      >
        {label}
      </span>
    </div>
  )
}

function WarningBox({ items }: { items: string[] }) {
  if (!items.length) return null
  return (
    <div className="rounded-md border border-amber-300/80 bg-amber-50/90 px-4 py-3 text-amber-950 shadow-sm">
      <h2 className="text-sm font-semibold text-amber-900">There were issues affecting this run of Lighthouse:</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-950/90">
        {items.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
    </div>
  )
}

function formatErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : String(x)))
      .join('; ')
  }
  if (detail && typeof detail === 'object' && 'detail' in detail) {
    return formatErrorDetail((detail as { detail: unknown }).detail)
  }
  return 'Request failed'
}

async function fetchReport(websiteUrl: string, batchId?: string): Promise<LighthouseReportPayload> {
  const u = new URL('/api/lighthouse/report', window.location.origin)
  u.searchParams.set('website_url', websiteUrl.trim())
  if (batchId?.trim()) u.searchParams.set('batch_id', batchId.trim())
  const res = await fetch(u.toString(), { credentials: 'include' })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      /* ignore */
    }
    const msg =
      body && typeof body === 'object' && 'detail' in body
        ? formatErrorDetail((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`
    throw new Error(msg)
  }
  return (await res.json()) as LighthouseReportPayload
}

export default function LighthouseReportPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialUrl = useMemo(() => {
    const q = searchParams.get('url')?.trim()
    return q && q.length >= 4 ? q : DEFAULT_WEBSITE_URL
  }, [searchParams])

  const [urlInput, setUrlInput] = useState(initialUrl)
  const [batchInput, setBatchInput] = useState(() => searchParams.get('batch_id') ?? '')
  const [submittedUrl, setSubmittedUrl] = useState(initialUrl)
  const [submittedBatch, setSubmittedBatch] = useState(() => searchParams.get('batch_id') ?? '')

  const syncQuery = useCallback(
    (nextUrl: string, nextBatch: string) => {
      const sp = new URLSearchParams(searchParams)
      sp.set('url', nextUrl.trim())
      if (nextBatch.trim()) sp.set('batch_id', nextBatch.trim())
      else sp.delete('batch_id')
      setSearchParams(sp, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const {
    data,
    isPending,
    isError,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['lighthouse-report', submittedUrl, submittedBatch || null],
    queryFn: () => fetchReport(submittedUrl, submittedBatch),
    staleTime: 60_000,
  })

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const u = urlInput.trim()
    if (u.length < 4) return
    setSubmittedUrl(u)
    setSubmittedBatch(batchInput)
    syncQuery(u, batchInput)
  }

  const scores = data?.scores

  return (
    <div className="min-h-0 min-w-0 overflow-auto rounded-lg border border-slate-300/80 bg-white p-4 shadow-sm sm:p-6">
      <form onSubmit={onSubmit} className="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <label className="flex min-w-[14rem] flex-1 flex-col gap-1 text-xs font-medium text-slate-700">
          Website URL
          <input
            type="url"
            name="website_url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-900 shadow-sm outline-none focus:border-teal-600 focus:ring-1 focus:ring-teal-600"
            placeholder="https://example.gov/"
            autoComplete="url"
          />
        </label>
        <label className="flex w-full min-w-[10rem] flex-col gap-1 text-xs font-medium text-slate-700 sm:w-48">
          Batch ID (optional)
          <input
            type="text"
            name="batch_id"
            value={batchInput}
            onChange={(e) => setBatchInput(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-900 shadow-sm outline-none focus:border-teal-600 focus:ring-1 focus:ring-teal-600"
            placeholder="from urls.meta.json"
          />
        </label>
        <button
          type="submit"
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white shadow hover:bg-teal-800 disabled:opacity-50"
          disabled={isFetching}
        >
          {isFetching ? 'Loading…' : 'Load report'}
        </button>
      </form>

      {isPending && (
        <p className="text-sm text-slate-600" role="status">
          Loading Lighthouse data…
        </p>
      )}

      {isError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900" role="alert">
          {(error as Error)?.message ?? 'Failed to load report'}
        </div>
      )}

      {data && scores && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-start justify-center gap-6 border-b border-slate-100 pb-6 sm:justify-between sm:gap-4">
            <LighthouseGauge label="Performance" score={scores.performance} />
            <LighthouseGauge label="Accessibility" score={scores.accessibility} />
            <LighthouseGauge label="Best Practices" score={scores.best_practices} />
            <LighthouseGauge label="SEO" score={scores.seo} />
          </div>

          <WarningBox items={data.run_warnings} />

          <section className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-start">
            <div>
              <LighthouseGauge label="Performance" score={scores.performance} size="lg" />
              <p className="mt-4 max-w-md text-xs leading-relaxed text-slate-600">
                Values are estimated and may vary. The performance score is calculated directly from these metrics.{' '}
                <a
                  href="https://googlechrome.github.io/lighthouse/scorecalc/"
                  className="text-teal-700 underline hover:text-teal-900"
                  target="_blank"
                  rel="noreferrer"
                >
                  See calculator
                </a>
                .
              </p>
              <dl className="mt-4 space-y-1 text-xs text-slate-600">
                <div>
                  <dt className="inline font-medium text-slate-700">Requested URL: </dt>
                  <dd className="inline break-all">{data.requested_url ?? data.website_url}</dd>
                </div>
                {data.final_url && data.final_url !== data.requested_url && (
                  <div>
                    <dt className="inline font-medium text-slate-700">Final URL: </dt>
                    <dd className="inline break-all">{data.final_url}</dd>
                  </div>
                )}
                <div>
                  <dt className="inline font-medium text-slate-700">Scanned at: </dt>
                  <dd className="inline">{data.scanned_at ?? '—'}</dd>
                </div>
                {data.lighthouse_version && (
                  <div>
                    <dt className="inline font-medium text-slate-700">Lighthouse: </dt>
                    <dd className="inline">{data.lighthouse_version}</dd>
                  </div>
                )}
              </dl>
            </div>
            <div className="flex flex-col items-center md:items-end">
              {data.screenshot_data_url ? (
                <figure className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50 shadow-md">
                  <img
                    src={data.screenshot_data_url}
                    alt="Mobile-sized screenshot from the Lighthouse report"
                    className="mx-auto max-h-[420px] w-auto max-w-full object-contain"
                  />
                  <figcaption className="border-t border-slate-200 px-2 py-1 text-center text-[10px] text-slate-500">
                    Final screenshot (from audit JSON)
                  </figcaption>
                </figure>
              ) : (
                <div className="flex min-h-[200px] w-full max-w-sm items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center text-sm text-slate-600">
                  No embedded screenshot in this run (run a full Lighthouse categories audit, not accessibility-only, to
                  capture <code className="text-xs">final-screenshot</code> in stored JSON).
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
