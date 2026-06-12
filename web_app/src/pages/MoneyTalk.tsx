import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { fetchMoneyAndTalk, type MoneyTalk, type MoneyTalkTheme } from '../api/moneyTalk'
import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { formatCurrency, formatNumber } from '../utils/formatters'

// Canonical colors per the contract.
const SPEND_COLOR = '#0d9488' // teal — money
const TALK_COLOR = '#d97706' // amber — talk / meetings
const UNDER_COLOR = '#7c3aed' // violet — under-discussed / over-funded

type ViewMode = 'overview' | 'trend' | 'race'
type Metric = 'money' | 'meetings' | 'compare'
type SortMode = 'budgets' | 'gaps'

// A bounded, repeating palette for per-theme trend lines.
const LINE_PALETTE = [
  '#0d9488',
  '#d97706',
  '#7c3aed',
  '#2563eb',
  '#dc2626',
  '#059669',
  '#db2777',
  '#ca8a04',
  '#0891b2',
  '#4f46e5',
]

function pct(n: number): string {
  return `${Math.round(n)}%`
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------
function OverviewView({
  themes,
  metric,
  sortMode,
}: {
  themes: MoneyTalkTheme[]
  metric: Metric
  sortMode: SortMode
}) {
  const sorted = useMemo(() => {
    const copy = [...themes]
    if (sortMode === 'gaps') {
      copy.sort((a, b) => b.talk_share - b.spend_share - (a.talk_share - a.spend_share))
    } else {
      copy.sort((a, b) => b.spend_share - a.spend_share)
    }
    return copy
  }, [themes, sortMode])

  if (sorted.length === 0) {
    return <EmptyState>No themes available.</EmptyState>
  }

  // Diverging (gap) mode — only used inside Compare.
  const diverging = metric === 'compare' && sortMode === 'gaps'
  const maxGap = useMemo(
    () => Math.max(1, ...sorted.map((t) => Math.abs(t.talk_share - t.spend_share))),
    [sorted],
  )

  return (
    <div className="space-y-3">
      {sorted.map((t) => {
        const gap = t.talk_share - t.spend_share
        return (
          <div
            key={`${t.theme}-${t.cofog_code ?? 'na'}`}
            className="rounded-lg border border-gray-200 bg-white p-4"
          >
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <h3 className="font-semibold text-gray-900">{t.theme}</h3>
              <span className="shrink-0 text-xs text-gray-400">
                {formatCurrency(t.spend_amount)} · {formatNumber(t.decision_count)} decisions
              </span>
            </div>

            {metric === 'compare' && !diverging && (
              <div className="space-y-1.5">
                {/* Spending bar */}
                <div className="flex items-center gap-2">
                  <span className="w-20 shrink-0 text-xs text-gray-500">Spending</span>
                  <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                    <div
                      className="h-full rounded"
                      style={{ width: `${Math.min(100, t.spend_share)}%`, backgroundColor: SPEND_COLOR }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right text-xs font-medium text-gray-700">
                    {pct(t.spend_share)}
                  </span>
                </div>
                {/* Talk bar */}
                <div className="flex items-center gap-2">
                  <span className="w-20 shrink-0 text-xs text-gray-500">Meetings</span>
                  <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                    <div
                      className="h-full rounded"
                      style={{ width: `${Math.min(100, t.talk_share)}%`, backgroundColor: TALK_COLOR }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right text-xs font-medium text-gray-700">
                    {pct(t.talk_share)}
                  </span>
                </div>
              </div>
            )}

            {diverging && (
              <div className="space-y-1">
                <div className="flex items-center">
                  {/* Left half — under-discussed / over-funded (violet) */}
                  <div className="flex h-5 flex-1 justify-end">
                    {gap < 0 && (
                      <div
                        className="h-full rounded-l"
                        style={{
                          width: `${(Math.abs(gap) / maxGap) * 100}%`,
                          backgroundColor: UNDER_COLOR,
                        }}
                      />
                    )}
                  </div>
                  <div className="h-5 w-px bg-gray-300" />
                  {/* Right half — over-discussed / under-funded (amber) */}
                  <div className="flex h-5 flex-1 justify-start">
                    {gap > 0 && (
                      <div
                        className="h-full rounded-r"
                        style={{
                          width: `${(Math.abs(gap) / maxGap) * 100}%`,
                          backgroundColor: TALK_COLOR,
                        }}
                      />
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">
                    talk {pct(t.talk_share)} vs spend {pct(t.spend_share)}
                  </span>
                  {gap >= 3 && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
                      style={{ backgroundColor: TALK_COLOR }}
                    >
                      Big topic, smaller budget
                    </span>
                  )}
                  {gap <= -3 && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
                      style={{ backgroundColor: UNDER_COLOR }}
                    >
                      Big budget, little discussion
                    </span>
                  )}
                </div>
              </div>
            )}

            {metric === 'money' && (
              <div className="flex items-center gap-2">
                <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                  <div
                    className="h-full rounded"
                    style={{ width: `${Math.min(100, t.spend_share)}%`, backgroundColor: SPEND_COLOR }}
                  />
                </div>
                <span className="w-28 shrink-0 text-right text-xs font-medium text-gray-700">
                  {pct(t.spend_share)} · {formatCurrency(t.spend_amount)}
                </span>
              </div>
            )}

            {metric === 'meetings' && (
              <div className="flex items-center gap-2">
                <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                  <div
                    className="h-full rounded"
                    style={{ width: `${Math.min(100, t.talk_share)}%`, backgroundColor: TALK_COLOR }}
                  />
                </div>
                <span className="w-32 shrink-0 text-right text-xs font-medium text-gray-700">
                  {pct(t.talk_share)} · {formatNumber(t.decision_count)} decisions
                </span>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Trend
// ---------------------------------------------------------------------------
function TrendView({ themes, metric }: { themes: MoneyTalkTheme[]; metric: Metric }) {
  // Discussion metric when "meetings", else spend amount.
  const useDiscussion = metric === 'meetings'

  // Themes with at least 2 monthly points.
  const eligible = useMemo(
    () => themes.filter((t) => (t.monthly?.length ?? 0) >= 2),
    [themes],
  )

  // Unified month axis = union of all months across eligible themes, sorted.
  const months = useMemo(() => {
    const set = new Set<string>()
    eligible.forEach((t) => t.monthly.forEach((m) => set.add(m.month)))
    return Array.from(set).sort()
  }, [eligible])

  const chartData = useMemo(() => {
    return months.map((month) => {
      const row: Record<string, string | number> = { month }
      eligible.forEach((t) => {
        const point = t.monthly.find((m) => m.month === month)
        if (point) {
          row[t.theme] = useDiscussion ? point.decision_count : point.spend_amount
        }
      })
      return row
    })
  }, [months, eligible, useDiscussion])

  if (eligible.length === 0 || months.length < 2) {
    return <EmptyState>Not enough monthly data to chart a trend yet.</EmptyState>
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="mb-3 text-xs text-gray-500">
        {useDiscussion ? 'Decisions per month' : 'Spending per month'} · {eligible.length} themes with
        enough history
      </p>
      <ResponsiveContainer width="100%" height={420}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => (useDiscussion ? formatNumber(v) : formatCurrency(v))}
            width={60}
          />
          <Tooltip
            formatter={(v: number) => (useDiscussion ? formatNumber(v) : formatCurrency(v))}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {eligible.map((t, i) => (
            <Line
              key={t.theme}
              type="monotone"
              dataKey={t.theme}
              stroke={LINE_PALETTE[i % LINE_PALETTE.length]}
              dot={false}
              connectNulls
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Race
// ---------------------------------------------------------------------------
const ROW_HEIGHT = 44

function RaceView({ themes, metric }: { themes: MoneyTalkTheme[]; metric: Metric }) {
  const useDiscussion = metric === 'meetings'

  const months = useMemo(() => {
    const set = new Set<string>()
    themes.forEach((t) => t.monthly.forEach((m) => set.add(m.month)))
    return Array.from(set).sort()
  }, [themes])

  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Clamp index when months change.
  useEffect(() => {
    setIdx((cur) => Math.min(cur, Math.max(0, months.length - 1)))
  }, [months.length])

  useEffect(() => {
    if (!playing) return
    timerRef.current = setInterval(() => {
      setIdx((cur) => {
        if (cur >= months.length - 1) {
          setPlaying(false)
          return cur
        }
        return cur + 1
      })
    }, 900)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [playing, months.length])

  const currentMonth = months[idx]

  const ranked = useMemo(() => {
    if (!currentMonth) return []
    const rows = themes.map((t) => {
      const point = t.monthly.find((m) => m.month === currentMonth)
      const value = point ? (useDiscussion ? point.decision_count : point.spend_amount) : 0
      return { theme: t.theme, value }
    })
    rows.sort((a, b) => b.value - a.value)
    return rows
  }, [themes, currentMonth, useDiscussion])

  if (months.length < 3) {
    return <EmptyState>Not enough monthly data to animate a ranking yet.</EmptyState>
  }

  const maxValue = Math.max(1, ...ranked.map((r) => r.value))

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={() => {
            if (idx >= months.length - 1) setIdx(0)
            setPlaying((p) => !p)
          }}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={months.length - 1}
          value={idx}
          onChange={(e) => {
            setPlaying(false)
            setIdx(Number(e.target.value))
          }}
          className="flex-1 accent-indigo-600"
        />
        <span className="w-20 shrink-0 text-right text-sm font-semibold tabular-nums text-gray-700">
          {currentMonth}
        </span>
      </div>

      <div className="relative" style={{ height: ranked.length * ROW_HEIGHT }}>
        {ranked.map((r, rank) => (
          <div
            key={r.theme}
            className="absolute left-0 right-0 flex items-center gap-2 transition-all duration-700 ease-out"
            style={{ top: rank * ROW_HEIGHT }}
          >
            <span className="w-40 shrink-0 truncate text-xs font-medium text-gray-700">
              {r.theme}
            </span>
            <div className="h-6 flex-1 overflow-hidden rounded bg-gray-100">
              <div
                className="flex h-full items-center justify-end rounded pr-2 text-[11px] font-semibold text-white transition-all duration-700 ease-out"
                style={{
                  width: `${Math.max(2, (r.value / maxValue) * 100)}%`,
                  backgroundColor: useDiscussion ? TALK_COLOR : SPEND_COLOR,
                }}
              >
                {r.value > 0
                  ? useDiscussion
                    ? formatNumber(r.value)
                    : formatCurrency(r.value)
                  : ''}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
function ToggleGroup<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === opt.value
              ? 'bg-indigo-600 text-white'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export default function MoneyTalk() {
  const [stateCode, setStateCode] = useState('')
  const [view, setView] = useState<ViewMode>('overview')
  const [metric, setMetric] = useState<Metric>('compare')
  const [sortMode, setSortMode] = useState<SortMode>('budgets')

  const { data, isLoading, isError, error } = useQuery<MoneyTalk>({
    queryKey: ['money-and-talk', stateCode],
    queryFn: () => fetchMoneyAndTalk(stateCode ? { state_code: stateCode } : undefined),
  })

  const themes = data?.themes ?? []

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">
          Spending vs discussion
        </p>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Money &amp; Talk</h1>
        {data?.note ? (
          <p className="text-gray-500 mb-2 max-w-3xl text-sm">{data.note}</p>
        ) : (
          <p className="text-gray-500 mb-2 max-w-3xl text-sm">
            Comparing each government function&apos;s share of spending against its share of meeting
            discussion.
          </p>
        )}
        {data?.as_of && (
          <p className="mb-6 text-xs text-gray-400">As of {data.as_of}</p>
        )}

        {/* Controls */}
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <ToggleGroup<ViewMode>
            value={view}
            onChange={setView}
            options={[
              { value: 'overview', label: 'Overview' },
              { value: 'trend', label: 'Trend' },
              { value: 'race', label: 'Race' },
            ]}
          />
          <ToggleGroup<Metric>
            value={metric}
            onChange={setMetric}
            options={[
              { value: 'money', label: 'Money' },
              { value: 'meetings', label: 'Meetings' },
              { value: 'compare', label: 'Compare' },
            ]}
          />
          {view === 'overview' && metric === 'compare' && (
            <ToggleGroup<SortMode>
              value={sortMode}
              onChange={setSortMode}
              options={[
                { value: 'budgets', label: 'Biggest budgets' },
                { value: 'gaps', label: 'Biggest gaps' },
              ]}
            />
          )}
          <select
            value={stateCode}
            onChange={(e) => setStateCode(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">National</option>
            {STATE_CODES.map((code) => (
              <option key={code} value={code}>
                {STATE_CODE_TO_NAME[code] ?? code}
              </option>
            ))}
          </select>
        </div>

        {/* Totals strip */}
        {data && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs text-gray-500">Decisions</div>
              <div className="text-xl font-bold text-gray-900">
                {data.totals.decision_count ? formatNumber(data.totals.decision_count) : '—'}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs text-gray-500">Money-flagged spend</div>
              <div className="text-xl font-bold text-gray-900">
                {data.totals.spend_amount ? formatCurrency(data.totals.spend_amount) : '—'}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs text-gray-500">Money-flagged decisions</div>
              <div className="text-xl font-bold text-gray-900">
                {data.totals.spend_count ? formatNumber(data.totals.spend_count) : '—'}
              </div>
            </div>
          </div>
        )}

        {/* Body */}
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Couldn&apos;t load Money &amp; Talk data.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : themes.length === 0 ? (
          <EmptyState>No data available for this selection.</EmptyState>
        ) : view === 'overview' ? (
          <OverviewView themes={themes} metric={metric} sortMode={sortMode} />
        ) : view === 'trend' ? (
          <TrendView themes={themes} metric={metric} />
        ) : (
          <RaceView themes={themes} metric={metric} />
        )}
      </div>
    </div>
  )
}
