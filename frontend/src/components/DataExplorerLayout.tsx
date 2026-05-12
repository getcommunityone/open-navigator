import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { DATA_EXPLORER_MAP_BASE, DATA_EXPLORER_SCORECARD } from '../utils/dataExplorerPaths'

function tabCls({ isActive }: { isActive: boolean }) {
  return [
    'inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'border-teal-600 text-teal-800'
      : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900',
  ].join(' ')
}

export default function DataExplorerLayout() {
  const { pathname } = useLocation()
  const onMap = pathname.startsWith(`${DATA_EXPLORER_MAP_BASE}/`) || pathname === DATA_EXPLORER_MAP_BASE
  const onScorecard = pathname.startsWith(DATA_EXPLORER_SCORECARD)

  return (
    <div className="flex min-h-[calc(100dvh-4.25rem)] flex-1 flex-col bg-slate-100">
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 min-h-0 flex-col px-3 py-3 sm:px-4 md:px-6 md:py-4">
        <header className="shrink-0 rounded-xl border border-slate-200 bg-white px-4 py-2.5 shadow-sm md:px-5 md:py-3">
          <h1 className="text-xl font-semibold text-slate-900">Data explorer</h1>
          <p className="mt-0.5 max-w-[52rem] text-xs leading-snug text-slate-600">
            American Community Survey (ACS) 5-year estimates — browse a map or read a location scorecard with multi-year
            trends and benchmarks.
          </p>
          <nav className="mt-2 flex flex-wrap gap-1" aria-label="Data explorer views">
            <NavLink to={DATA_EXPLORER_MAP_BASE} className={tabCls}>
              Map view
            </NavLink>
            <NavLink to={DATA_EXPLORER_SCORECARD} className={tabCls}>
              Scorecard
            </NavLink>
          </nav>
          {(onMap || onScorecard) && (
            <p className="mt-1 pb-0.5 text-[11px] text-slate-500" aria-live="polite">
              {onMap
                ? 'Choropleth and drill-downs match the static census map bundle.'
                : 'Trend windows follow the vintage list in the published bundle (1-, 3-, and 5-year lookbacks when years exist).'}
            </p>
          )}
        </header>

        {/* Grey workspace: explicit panel so map/scorecard white tiles sit on visible slate, not page white */}
        <div className="mt-3 min-h-0 min-w-0 flex-1 rounded-xl border border-slate-200/90 bg-slate-100 p-2 shadow-sm sm:mt-4 sm:p-3 md:p-4">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
