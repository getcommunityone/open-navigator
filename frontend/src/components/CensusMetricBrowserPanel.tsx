import { useEffect, useMemo, useState } from 'react'
import {
  AcademicCapIcon,
  BanknotesIcon,
  BriefcaseIcon,
  ChevronLeftIcon,
  HomeModernIcon,
  LifebuoyIcon,
  MinusIcon,
  PlusIcon,
  Squares2X2Icon,
  UsersIcon,
} from '@heroicons/react/24/outline'
import { InfoHelpTrigger } from './InfoHelpTrigger'
import { groupMetricsForBrowser, groupIdForMetric } from '../utils/censusMetricGroups'

/**
 * Leading glyph per metric group, keyed by the taxonomy's group id
 * (../utils/censusMetricGroups). Anything without an explicit entry — including
 * the trailing "Other measures" bucket — falls back to a neutral grid icon.
 */
const GROUP_ICONS: Record<string, typeof BanknotesIcon> = {
  income: BanknotesIcon,
  housing: HomeModernIcon,
  people: UsersIcon,
  poverty_insurance: LifebuoyIcon,
  education: AcademicCapIcon,
  work: BriefcaseIcon,
}

interface CensusMetricBrowserPanelProps {
  metrics: ReadonlyArray<{ slug: string; label: string }>
  metricSlug: string
  metricFullHelp: string
  onPick: (slug: string) => void
  /** Collapse the panel back to the bare rail. */
  onCollapse: () => void
}

/**
 * Persistent, collapsible metric browser that sits beside the map's display
 * rail. Metrics are organised by the shared topic taxonomy
 * (../utils/censusMetricGroups); the category owning the active metric starts
 * expanded so the current selection is always visible without hunting. Unlike
 * the old header ``<select>``, this keeps the full metric tree on screen, which
 * is the desktop interaction the mockup specifies. The header dropdown remains
 * the small-screen affordance — this panel is rendered desktop-only by the page.
 */
export default function CensusMetricBrowserPanel({
  metrics,
  metricSlug,
  metricFullHelp,
  onPick,
  onCollapse,
}: CensusMetricBrowserPanelProps) {
  const groups = useMemo(() => groupMetricsForBrowser(metrics), [metrics])

  // Track which categories are expanded. The group holding the active metric is
  // opened on mount and whenever the selection jumps to a different group (e.g.
  // via the URL), without stomping a user's manual expand/collapse elsewhere.
  const activeGroupId = groupIdForMetric(metricSlug)
  const [open, setOpen] = useState<Record<string, boolean>>(() => ({ [activeGroupId]: true }))
  useEffect(() => {
    setOpen((prev) => (prev[activeGroupId] ? prev : { ...prev, [activeGroupId]: true }))
  }, [activeGroupId])

  return (
    <div className="flex h-full w-60 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-3 py-2.5">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          Metrics
          <InfoHelpTrigger help={metricFullHelp} topic="Metric" align="left" />
        </span>
        <button
          type="button"
          onClick={onCollapse}
          className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          aria-label="Collapse metric panel"
          title="Collapse metric panel"
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain p-2">
        {groups.map((g) => {
          const isOpen = !!open[g.id]
          const Icon = GROUP_ICONS[g.id] ?? Squares2X2Icon
          return (
            <div key={g.id} className="overflow-hidden rounded-lg border border-slate-200">
              <button
                type="button"
                onClick={() => setOpen((prev) => ({ ...prev, [g.id]: !prev[g.id] }))}
                className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-[13px] font-semibold text-slate-800 hover:bg-slate-50"
                aria-expanded={isOpen}
              >
                <Icon className="h-[18px] w-[18px] shrink-0 text-slate-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate">{g.title}</span>
                {isOpen ? (
                  <MinusIcon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                ) : (
                  <PlusIcon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                )}
              </button>
              {isOpen ? (
                <ul className="border-t border-slate-200 p-1.5">
                  {g.metrics.map((m) => {
                    const selected = m.slug === metricSlug
                    return (
                      <li key={m.slug}>
                        <button
                          type="button"
                          onClick={() => onPick(m.slug)}
                          aria-current={selected ? 'true' : undefined}
                          className={`block w-full rounded-md px-2 py-1.5 pl-3.5 text-left text-[12.5px] leading-snug ${
                            selected
                              ? 'bg-[#354F52] font-medium text-white'
                              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                          }`}
                        >
                          {m.label}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
