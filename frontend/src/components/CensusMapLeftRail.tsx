import {
  AdjustmentsHorizontalIcon,
  ArrowUturnLeftIcon,
  CalendarDaysIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  MapIcon,
  SwatchIcon,
} from '@heroicons/react/24/outline'

export type CensusMapRailSection = 'year' | 'view' | 'scale' | 'values'

interface CensusMapLeftRailProps {
  activeSection: CensusMapRailSection | null
  /**
   * Open a display control. ``anchorRect`` is the clicked button's viewport
   * rect, so callers that render the control as a rail-anchored popover can
   * position it; callers using a drawer can ignore it.
   */
  onOpen: (section: CensusMapRailSection, anchorRect?: DOMRect) => void
  /** Tag shown next to the year icon, e.g. "2024". Truncated if long. */
  yearBadge?: string
  /** Resets the map to the nation view. Disabled when already there. */
  onReset?: () => void
  /** True if there's anywhere to reset to (i.e. user has zoomed in). */
  canReset?: boolean
  /**
   * When provided, renders a bottom toggle for the adjacent metric panel.
   * ``metricPanelOpen`` drives the icon direction. Omit on surfaces without a
   * metric browser (the icon simply doesn't render).
   */
  onToggleMetricPanel?: () => void
  metricPanelOpen?: boolean
}

interface RailItem {
  id: CensusMapRailSection
  label: string
  hint: string
  icon: typeof CalendarDaysIcon
}

const RAIL_ITEMS: RailItem[] = [
  { id: 'year', label: 'Year', hint: 'ACS end year and play through history', icon: CalendarDaysIcon },
  { id: 'view', label: 'View', hint: 'Filled map vs bubbles', icon: MapIcon },
  { id: 'scale', label: 'Color', hint: 'How values stretch across colors', icon: SwatchIcon },
  { id: 'values', label: 'Numbers', hint: 'Raw, year-over-year, or vs national', icon: AdjustmentsHorizontalIcon },
]

export default function CensusMapLeftRail({
  activeSection,
  onOpen,
  yearBadge,
  onReset,
  canReset = false,
  onToggleMetricPanel,
  metricPanelOpen = true,
}: CensusMapLeftRailProps) {
  return (
    <nav
      className="flex h-full flex-col items-stretch gap-1 rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm"
      aria-label="Map display options"
    >
      {onReset ? (
        <>
          <button
            type="button"
            onClick={onReset}
            disabled={!canReset}
            title={canReset ? 'Reset map to United States view' : 'Already at United States view'}
            aria-label="Reset map to nation view"
            className={`group relative flex w-12 flex-col items-center gap-0.5 rounded-lg px-1.5 py-2 text-[10px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-1 ${
              canReset
                ? 'bg-amber-50 text-amber-800 hover:bg-amber-100'
                : 'cursor-not-allowed text-slate-300'
            }`}
          >
            <ArrowUturnLeftIcon className="h-5 w-5" aria-hidden />
            <span className="leading-none">Reset</span>
          </button>
          <div className="my-0.5 h-px bg-slate-200" aria-hidden />
        </>
      ) : null}
      {RAIL_ITEMS.map((it) => {
        const active = activeSection === it.id
        const Icon = it.icon
        return (
          <button
            key={it.id}
            type="button"
            onClick={(e) => onOpen(it.id, e.currentTarget.getBoundingClientRect())}
            title={`${it.label} — ${it.hint}`}
            aria-label={`${it.label}: ${it.hint}`}
            className={`group relative flex w-12 flex-col items-center gap-0.5 rounded-lg px-1.5 py-2 text-[10px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-1 ${
              active
                ? 'bg-[#354F52] text-white shadow-inner'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Icon className="h-5 w-5" aria-hidden />
            <span className="leading-none">{it.label}</span>
            {it.id === 'year' && yearBadge ? (
              <span
                className={`mt-0.5 rounded-full px-1.5 py-px text-[9px] tabular-nums leading-none ${
                  active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700'
                }`}
              >
                {yearBadge}
              </span>
            ) : null}
          </button>
        )
      })}
      {onToggleMetricPanel ? (
        <>
          {/* Spacer pushes the panel toggle to the bottom, separating it from
              the display controls above so it reads as a sidebar collapse. */}
          <div className="mt-auto" aria-hidden />
          <div className="my-0.5 h-px bg-slate-200" aria-hidden />
          <button
            type="button"
            onClick={onToggleMetricPanel}
            title={metricPanelOpen ? 'Hide metric list' : 'Show metric list'}
            aria-label={metricPanelOpen ? 'Hide metric list' : 'Show metric list'}
            aria-pressed={metricPanelOpen}
            className={`group relative flex w-12 flex-col items-center gap-0.5 rounded-lg px-1.5 py-2 text-[10px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-1 ${
              metricPanelOpen
                ? 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                : 'bg-[#354F52] text-white shadow-inner hover:bg-[#2b4042]'
            }`}
          >
            {metricPanelOpen ? (
              <ChevronDoubleLeftIcon className="h-5 w-5" aria-hidden />
            ) : (
              <ChevronDoubleRightIcon className="h-5 w-5" aria-hidden />
            )}
            <span className="leading-none">{metricPanelOpen ? 'Hide' : 'Metrics'}</span>
          </button>
        </>
      ) : null}
    </nav>
  )
}
