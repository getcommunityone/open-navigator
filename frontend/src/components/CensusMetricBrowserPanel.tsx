import { useEffect, useMemo, useState } from 'react'
import {
  BuildingLibraryIcon,
  ChartBarIcon,
  ChevronLeftIcon,
  HeartIcon,
  MinusIcon,
  PlusIcon,
  ShieldCheckIcon,
  Squares2X2Icon,
  UsersIcon,
} from '@heroicons/react/24/outline'
import { InfoHelpTrigger } from './InfoHelpTrigger'
import { groupMetricsByTheme, themeIdForMetric } from '../utils/censusMetricGroups'

/**
 * Leading glyph per top-level theme, keyed by the taxonomy's theme id
 * (../utils/censusMetricGroups). Anything without an explicit entry — including
 * the trailing "More measures" bucket — falls back to a neutral grid icon.
 */
const THEME_ICONS: Record<string, typeof ChartBarIcon> = {
  economy: ChartBarIcon,
  people: UsersIcon,
  health: HeartIcon,
  crime: ShieldCheckIcon,
  government: BuildingLibraryIcon,
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
 * rail. Metrics are organised into two levels — top-level themes (Economy,
 * People, Health, …) each holding sub-grouped metrics (Income, Housing, …) —
 * from the shared taxonomy (../utils/censusMetricGroups). The theme owning the
 * active metric starts expanded so the current selection is always visible.
 * Collapsed themes show a "+"; expanded themes show "−". Themes with no metrics
 * yet (Crime, Government) still expand, to an empty placeholder. The header
 * dropdown remains the small-screen affordance — this panel is desktop-only.
 */
export default function CensusMetricBrowserPanel({
  metrics,
  metricSlug,
  metricFullHelp,
  onPick,
  onCollapse,
}: CensusMetricBrowserPanelProps) {
  const themes = useMemo(() => groupMetricsByTheme(metrics), [metrics])

  // Track which themes are expanded. The theme holding the active metric is
  // opened on mount and whenever the selection jumps to a different theme (e.g.
  // via the URL), without stomping a user's manual expand/collapse elsewhere.
  const activeThemeId = themeIdForMetric(metricSlug)
  const [open, setOpen] = useState<Record<string, boolean>>(() => ({ [activeThemeId]: true }))
  useEffect(() => {
    setOpen((prev) => (prev[activeThemeId] ? prev : { ...prev, [activeThemeId]: true }))
  }, [activeThemeId])

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
        {themes.map((t) => {
          const isOpen = !!open[t.id]
          const Icon = THEME_ICONS[t.id] ?? Squares2X2Icon
          return (
            <div key={t.id} className="overflow-hidden rounded-lg border border-slate-200">
              <button
                type="button"
                onClick={() => setOpen((prev) => ({ ...prev, [t.id]: !prev[t.id] }))}
                className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-[13px] font-semibold text-slate-800 hover:bg-slate-50"
                aria-expanded={isOpen}
              >
                <Icon className="h-[18px] w-[18px] shrink-0 text-slate-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate">{t.title}</span>
                {/* Expand/collapse affordance — "+" stays visible when collapsed. */}
                {isOpen ? (
                  <MinusIcon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                ) : (
                  <PlusIcon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                )}
              </button>
              {isOpen ? (
                <div className="border-t border-slate-200 p-1.5">
                  {t.groups.length === 0 ? (
                    <p className="px-2 py-2 text-[12px] italic leading-snug text-slate-400">
                      No metrics yet
                    </p>
                  ) : (
                    t.groups.map((g) => (
                      <div key={g.id} className="mb-1 last:mb-0">
                        <div className="px-2 pb-0.5 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                          {g.shortTitle ?? g.title}
                        </div>
                        <ul>
                          {g.metrics.map((m) => {
                            const selected = m.slug === metricSlug
                            return (
                              <li key={m.slug}>
                                <button
                                  type="button"
                                  onClick={() => onPick(m.slug)}
                                  aria-current={selected ? 'true' : undefined}
                                  className={`block w-full rounded-md px-2 py-1.5 text-left text-[12.5px] leading-snug ${
                                    selected
                                      ? 'bg-indigo-100 font-medium text-indigo-900'
                                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                                  }`}
                                >
                                  {m.label}
                                </button>
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
