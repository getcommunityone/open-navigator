import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api, { apiBaseUrl } from '../lib/api'
import { formatCurrency } from '../utils/formatters'
import {
  ArrowTopRightOnSquareIcon,
  BuildingOffice2Icon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'

// Mirrors api/routes/efile990.py -> Efile990
interface Address {
  line1?: string | null
  line2?: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
  country?: string | null
}
interface Filer {
  ein?: string | null
  name?: string | null
  phone?: string | null
  address?: Address | null
}
interface Header {
  return_type?: string | null
  tax_year?: string | null
  tax_period_begin?: string | null
  tax_period_end?: string | null
  return_ts?: string | null
  filer: Filer
  officer: { name?: string | null; title?: string | null }
  preparer: Record<string, unknown>
}
interface OfficerComp {
  name?: string | null
  title?: string | null
  avg_hours_per_week?: string | null
  reportable_comp_org?: number | null
  reportable_comp_related?: number | null
  other_comp?: number | null
}
interface Grant {
  recipient_name?: string | null
  recipient_ein?: string | null
  irc_section?: string | null
  cash_grant?: number | null
  non_cash_assistance?: string | null
  purpose?: string | null
}
interface Efile990 {
  object_id?: string | null
  source_url?: string | null
  return_version?: string | null
  header: Header
  summary: Record<string, unknown>
  officers: OfficerComp[]
  grants: Grant[]
  schedules: string[]
  sections: Record<string, unknown>
}

const SAMPLE_OBJECT_ID = '201602229349300615'

// Curated headline financials (label + key into `summary`). Amounts are dollars.
const SUMMARY_MONEY: Array<{ key: string; label: string }> = [
  { key: 'total_revenue_cy', label: 'Total revenue' },
  { key: 'total_expenses_cy', label: 'Total expenses' },
  { key: 'revenue_less_expenses_cy', label: 'Revenue less expenses' },
  { key: 'contributions_grants_cy', label: 'Contributions & grants' },
  { key: 'program_service_revenue_cy', label: 'Program service revenue' },
  { key: 'grants_paid_cy', label: 'Grants paid' },
  { key: 'salaries_etc_cy', label: 'Salaries & benefits' },
  { key: 'gross_receipts', label: 'Gross receipts' },
  { key: 'total_assets_eoy', label: 'Total assets (EOY)' },
  { key: 'total_liabilities_eoy', label: 'Total liabilities (EOY)' },
  { key: 'net_assets_eoy', label: 'Net assets (EOY)' },
]
const SUMMARY_COUNTS: Array<{ key: string; label: string }> = [
  { key: 'employee_count', label: 'Employees' },
  { key: 'volunteer_count', label: 'Volunteers' },
  { key: 'voting_members', label: 'Voting members' },
  { key: 'voting_members_independent', label: 'Independent members' },
]

function asNumber(v: unknown): number | null {
  return typeof v === 'number' ? v : null
}

/** Collapsible, recursive renderer for the loss-less generic section tree. */
function JsonNode({ name, value }: { name: string; value: unknown }) {
  const [open, setOpen] = useState(false)
  const isObject = value !== null && typeof value === 'object'

  if (!isObject) {
    return (
      <div className="flex gap-2 py-0.5 text-sm">
        <span className="text-gray-500 shrink-0">{name}:</span>
        <span className="text-gray-900 break-words">{String(value)}</span>
      </div>
    )
  }

  const entries = Array.isArray(value)
    ? value.map((v, i) => [String(i), v] as const)
    : Object.entries(value as Record<string, unknown>)

  return (
    <div className="py-0.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        <span className="inline-block w-3 text-gray-400">{open ? '▾' : '▸'}</span>
        {name}
        <span className="text-xs text-gray-400">
          {Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`}
        </span>
      </button>
      {open && (
        <div className="ml-4 border-l border-gray-200 pl-3">
          {entries.map(([k, v]) => (
            <JsonNode key={k} name={k} value={v} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Efile990Viewer() {
  const { objectId } = useParams<{ objectId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<Efile990 | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [inputId, setInputId] = useState(objectId || SAMPLE_OBJECT_ID)

  useEffect(() => {
    if (!objectId) {
      setData(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    api
      .get<Efile990>(`/efile990/${objectId}`)
      .then((r) => {
        if (!cancelled) {
          setData(r.data)
          setIsLoading(false)
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message || 'Failed to load return')
          setIsLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [objectId])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const id = inputId.trim()
    if (/^\d{8,32}$/.test(id)) navigate(`/efile990/${id}`)
    else setError('Enter a numeric object id (e.g. 201602229349300615)')
  }

  const header = data?.header
  const filer = header?.filer
  const addr = filer?.address

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">IRS Form 990 e-file viewer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Parses a raw return from the GivingTuesday 990 data lake by its object id.
        </p>
      </div>

      <form onSubmit={submit} className="flex gap-2 mb-8">
        <input
          value={inputId}
          onChange={(e) => setInputId(e.target.value)}
          placeholder="Object id, e.g. 201602229349300615"
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <MagnifyingGlassIcon className="h-4 w-4" />
          View
        </button>
      </form>

      {isLoading && <div className="text-gray-500">Loading return…</div>}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {!objectId && !error && (
        <div className="text-sm text-gray-500">
          Enter an object id above to view a filing.
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-8">
          {/* Filer / header card */}
          <section className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-gray-400 text-xs uppercase tracking-wide mb-1">
                  <BuildingOffice2Icon className="h-4 w-4" />
                  Form {header?.return_type} · Tax year {header?.tax_year}
                </div>
                <h2 className="text-xl font-bold text-gray-900">{filer?.name || '—'}</h2>
                <div className="text-sm text-gray-600 mt-1">
                  {filer?.ein && <span>EIN {filer.ein}</span>}
                  {addr?.city && (
                    <span>
                      {filer?.ein ? ' · ' : ''}
                      {addr.city}
                      {addr.state ? `, ${addr.state}` : ''}
                    </span>
                  )}
                </div>
                {(header?.tax_period_begin || header?.tax_period_end) && (
                  <div className="text-xs text-gray-500 mt-1">
                    Period {header?.tax_period_begin} → {header?.tax_period_end}
                  </div>
                )}
              </div>
              {data.source_url && (
                <a
                  href={data.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 shrink-0"
                >
                  Raw XML
                  <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                </a>
              )}
            </div>

            {typeof data.summary.mission === 'string' && data.summary.mission && (
              <p className="mt-4 text-sm text-gray-700 border-t border-gray-100 pt-4">
                {data.summary.mission}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {typeof data.summary.website === 'string' && data.summary.website && (
                <span className="text-xs text-gray-500">{data.summary.website}</span>
              )}
              {data.schedules.map((s) => (
                <span
                  key={s}
                  className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600"
                >
                  {s.replace('IRS990', '') || '990'}
                </span>
              ))}
            </div>
          </section>

          {/* Financial summary */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Financial summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {SUMMARY_MONEY.filter((f) => asNumber(data.summary[f.key]) !== null).map((f) => (
                <div key={f.key} className="rounded-lg border border-gray-200 bg-white p-4">
                  <div className="text-xs text-gray-500">{f.label}</div>
                  <div className="text-lg font-semibold text-gray-900">
                    {formatCurrency(asNumber(data.summary[f.key]))}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-4">
              {SUMMARY_COUNTS.filter((f) => asNumber(data.summary[f.key]) !== null).map((f) => (
                <div key={f.key} className="text-sm">
                  <span className="text-gray-500">{f.label}: </span>
                  <span className="font-semibold text-gray-900">
                    {asNumber(data.summary[f.key])}
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Officers */}
          {data.officers.length > 0 && (
            <section>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Officers, directors & key employees ({data.officers.length})
              </h3>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Name</th>
                      <th className="px-4 py-2 font-medium">Title</th>
                      <th className="px-4 py-2 font-medium text-right">Hrs/wk</th>
                      <th className="px-4 py-2 font-medium text-right">Comp (org)</th>
                      <th className="px-4 py-2 font-medium text-right">Other comp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {data.officers.map((o, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-medium text-gray-900">{o.name}</td>
                        <td className="px-4 py-2 text-gray-600">{o.title}</td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {o.avg_hours_per_week ?? '—'}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-900">
                          {formatCurrency(o.reportable_comp_org)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {formatCurrency(o.other_comp)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Grants (Schedule I) */}
          {data.grants.length > 0 && (
            <section>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Grants to organizations ({data.grants.length})
              </h3>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Recipient</th>
                      <th className="px-4 py-2 font-medium">EIN</th>
                      <th className="px-4 py-2 font-medium text-right">Cash grant</th>
                      <th className="px-4 py-2 font-medium">Purpose</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {data.grants.map((g, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-medium text-gray-900">{g.recipient_name}</td>
                        <td className="px-4 py-2 text-gray-600">{g.recipient_ein ?? '—'}</td>
                        <td className="px-4 py-2 text-right text-gray-900">
                          {formatCurrency(g.cash_grant)}
                        </td>
                        <td className="px-4 py-2 text-gray-600 max-w-md">{g.purpose}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Full return tree */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Full return</h3>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              {Object.entries(data.sections).map(([name, value]) => (
                <JsonNode key={name} name={name} value={value} />
              ))}
            </div>
            <p className="mt-2 text-xs text-gray-400">
              Source: <code>{`${apiBaseUrl}/efile990/${data.object_id}/raw`}</code>
              {data.return_version ? ` · version ${data.return_version}` : ''}
            </p>
          </section>
        </div>
      )}
    </div>
  )
}
