import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  DATA_EXPLORER_JURISDICTION_QUALITY,
  DATA_EXPLORER_LIGHTHOUSE_REPORT,
  DATA_EXPLORER_MAP_BASE,
  DATA_EXPLORER_SCORECARD,
} from '../utils/dataExplorerPaths'

function tabCls({ isActive }: { isActive: boolean }) {
  return [
    'inline-flex items-center gap-1.5 border-b-2 px-2.5 py-1.5 text-sm font-medium transition-colors',
    isActive
      ? 'border-teal-600 text-teal-800'
      : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900',
  ].join(' ')
}

export default function DataExplorerLayout() {
  const { pathname } = useLocation()
  const onMap = pathname.startsWith(`${DATA_EXPLORER_MAP_BASE}/`) || pathname === DATA_EXPLORER_MAP_BASE
  const onScorecard = pathname.startsWith(DATA_EXPLORER_SCORECARD)
  const onJurisdictionQuality =
    pathname === DATA_EXPLORER_JURISDICTION_QUALITY || pathname.startsWith(`${DATA_EXPLORER_JURISDICTION_QUALITY}/`)
  const onLighthouseReport =
    pathname === DATA_EXPLORER_LIGHTHOUSE_REPORT || pathname.startsWith(`${DATA_EXPLORER_LIGHTHOUSE_REPORT}/`)

  return (
    <div className="flex min-h-[calc(100dvh-4.25rem)] flex-1 flex-col bg-slate-200">
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 min-h-0 flex-col px-3 py-2 sm:px-4 md:px-5 md:py-3">
        <header className="shrink-0 rounded-lg border border-slate-300/80 bg-white px-3 py-2 shadow-sm sm:px-4 sm:py-2">
          <h1 className="text-lg font-semibold leading-tight text-slate-900 sm:text-xl">Data explorer</h1>
          <p className="mt-0.5 max-w-[52rem] text-[11px] leading-snug text-slate-600 sm:text-xs">
            American Community Survey (ACS) 5-year estimates — map and scorecard — plus jurisdiction website mapping
            coverage (counties, cities, school districts) from directory seeds and dbt marts.
          </p>
          <nav
            className="mt-1.5 -mx-1 flex gap-1 overflow-x-auto px-1 pb-0.5 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
            aria-label="Data explorer views"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            <NavLink
              to={DATA_EXPLORER_MAP_BASE}
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Map view
            </NavLink>
            <NavLink
              to={DATA_EXPLORER_SCORECARD}
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Scorecard
            </NavLink>
            <NavLink
              to={DATA_EXPLORER_JURISDICTION_QUALITY}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Data quality
            </NavLink>
            <NavLink
              to={DATA_EXPLORER_LIGHTHOUSE_REPORT}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Lighthouse report
            </NavLink>
          </nav>
          {(onMap || onScorecard || onJurisdictionQuality || onLighthouseReport) && (
            <p className="mt-0.5 text-[10px] leading-snug text-slate-600 sm:text-[11px]" aria-live="polite">
              {onMap
                ? 'Choropleth and drill-downs match the static census map bundle.'
                : onScorecard
                  ? 'Trend windows follow the vintage list in the published bundle (1-, 3-, and 5-year lookbacks when years exist).'
                  : onLighthouseReport
                    ? 'Scores and warnings are read from the latest `bronze.bronze_jurisdiction_website_lighthouse` row for the URL you enter (after accessibility lighthouse ingest).'
                    : 'Mapping rates use NACo, USCM, NCES directory, GSA .gov, Wikidata, and overrides — snapshot from `frontend/public/data/jurisdiction_mapping_quality.json`.'}
            </p>
          )}
        </header>

        {/* Workspace: mid-slate so white cards read clearly (slate-100 alone looked “all white”). */}
        <div className="mt-2 min-h-0 min-w-0 flex-1 rounded-xl border border-slate-400/50 bg-slate-300/40 p-1.5 shadow-inner sm:mt-2 sm:p-2 md:p-2.5">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
