import { useParams, useSearchParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import MeetingPlayer from '../components/MeetingPlayer'
import {
  ArrowLeftIcon,
  BuildingLibraryIcon,
  CalendarIcon,
  MapPinIcon,
  ScaleIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline'

interface MeetingDecision {
  event_decision_id: string
  headline?: string | null
  outcome?: string | null
  primary_theme?: string | null
}

interface MeetingFinancialItem {
  event_financial_item_id: string
  financial_item_id?: string | null
  event_description?: string | null
  amount?: number | null
  amount_type?: string | null
}

interface MeetingDetailData {
  event_meeting_id: number
  c1_event_id?: string | null
  body_name?: string | null
  jurisdiction_name?: string | null
  jurisdiction_type?: string | null
  state?: string | null
  state_code?: string | null
  meeting_date?: string | null
  video_id?: string | null
  decisions: MeetingDecision[]
  financial_items: MeetingFinancialItem[]
}

function money(value?: number | null): string {
  if (value == null) return '—'
  const sign = value < 0 ? '-' : ''
  const n = Math.abs(value)
  if (n >= 1_000_000) return `${sign}$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${sign}$${(n / 1_000).toFixed(1)}K`
  return `${sign}$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function outcomeColor(outcome?: string | null): string {
  const o = (outcome || '').toLowerCase()
  if (/(approv|pass|adopt|grant)/.test(o)) return 'bg-green-100 text-green-800'
  if (/(defer|table|postpon|continu|hold)/.test(o)) return 'bg-yellow-100 text-yellow-800'
  if (/(den|reject|fail|veto|withdraw)/.test(o)) return 'bg-red-100 text-red-800'
  return 'bg-gray-100 text-gray-800'
}

export default function MeetingDetail() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const highlightItem = searchParams.get('item') // financial_item_id to spotlight
  const navigate = useNavigate()
  const routerLoc = useLocation()
  const goBack = () => {
    if (routerLoc.key && routerLoc.key !== 'default') navigate(-1)
    else navigate('/search')
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['meeting', id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get(`/meeting/${id}`)
      return res.data as MeetingDetailData
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="h-40 animate-pulse rounded-lg bg-white shadow-sm" />
        </div>
      </div>
    )
  }

  if (isError || !data) {
    const msg = (error as { message?: string } | undefined)?.message || 'This meeting could not be loaded.'
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Meeting not found</h3>
            <p className="text-red-700 mb-4">{msg}</p>
            <Link
              to="/search"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              Back to Search
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const place = data.jurisdiction_name || data.state || ''
  const caption = [data.body_name, data.meeting_date].filter(Boolean).join(' · ')

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <button
          type="button"
          onClick={goBack}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-[#1d6b5f] mb-2">
            <BuildingLibraryIcon className="h-4 w-4" />
            Meeting
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{data.body_name || 'Civic meeting'}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
            {place && (
              <span className="inline-flex items-center gap-1.5">
                <MapPinIcon className="h-4 w-4 text-gray-400" />
                {place}
                {data.state_code ? `, ${data.state_code}` : ''}
              </span>
            )}
            {data.meeting_date && (
              <span className="inline-flex items-center gap-1.5">
                <CalendarIcon className="h-4 w-4 text-gray-400" />
                {data.meeting_date}
              </span>
            )}
          </div>
        </div>

        {/* Recording + transcript */}
        {data.video_id && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Watch the meeting</h2>
            <MeetingPlayer videoId={data.video_id} caption={caption} />
          </div>
        )}

        {/* Financial items */}
        {data.financial_items.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <BanknotesIcon className="h-5 w-5 text-[#1d6b5f]" />
              Money discussed
              <span className="text-sm font-normal text-gray-400">({data.financial_items.length})</span>
            </h2>
            <div className="divide-y divide-gray-100">
              {data.financial_items.map((fi) => {
                const isHighlight = !!highlightItem && fi.financial_item_id === highlightItem
                return (
                  <div
                    key={fi.event_financial_item_id}
                    className={`flex items-start gap-4 py-3 ${
                      isHighlight ? '-mx-3 rounded-lg border border-[#e3dcf5] bg-[#f4f0fc] px-3' : ''
                    }`}
                  >
                    <div className="shrink-0 text-right">
                      <div className="text-[15px] font-bold text-[#16201d]">{money(fi.amount)}</div>
                      {fi.amount_type && (
                        <div className="text-[11px] text-gray-400">{fi.amount_type}</div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm text-gray-700">{fi.event_description || 'Financial item'}</p>
                      {isHighlight && (
                        <span className="mt-1 inline-block rounded-full bg-[#efebfb] px-2 py-0.5 text-[11px] font-semibold text-[#6b5bd2]">
                          Flagged: sits just under the approval limit
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Decisions */}
        {data.decisions.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <ScaleIcon className="h-5 w-5 text-[#1d6b5f]" />
              Decisions at this meeting
              <span className="text-sm font-normal text-gray-400">({data.decisions.length})</span>
            </h2>
            <div className="space-y-2">
              {data.decisions.map((d) => (
                <Link
                  key={d.event_decision_id}
                  to={`/decisions/${d.event_decision_id}`}
                  className="flex items-center gap-3 rounded-lg border border-gray-100 px-4 py-3 transition-colors hover:border-[#cfe0db] hover:bg-[#f7fafb]"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-gray-900">
                      {d.headline || 'Decision'}
                    </div>
                    {d.primary_theme && (
                      <div className="text-xs text-gray-400">{d.primary_theme}</div>
                    )}
                  </div>
                  {d.outcome && (
                    <span
                      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${outcomeColor(
                        d.outcome,
                      )}`}
                    >
                      {d.outcome}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}

        {data.decisions.length === 0 && data.financial_items.length === 0 && !data.video_id && (
          <div className="rounded-lg border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
            No decisions or financial items were recorded for this meeting.
          </div>
        )}
      </div>
    </div>
  )
}
