import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom'
import { tracer } from './instrumentation'
import Layout from './components/Layout'
import Home from './pages/Home'
import HomeModern from './pages/HomeModern'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import Heatmap from './pages/Heatmap'
import Documents from './pages/Documents'
import Opportunities from './pages/Opportunities'
import Nonprofits from './pages/Nonprofits'
import NonprofitsHF from './pages/NonprofitsHF'
import Settings from './pages/Settings'
import PeopleFinder from './pages/PeopleFinder'
import PersonDetail from './pages/PersonDetail'
import DebateFinder from './pages/DebateGrader'
import Profile from './pages/Profile'
import Explore from './pages/Explore'
import Events from './pages/Events'
import Services from './pages/Services'
import Developers from './pages/Developers'
import JurisdictionMappingQualityPage from './pages/JurisdictionMappingQualityPage'
import LighthouseReportPage from './pages/LighthouseReportPage'
import BatchJobStatusPage from './pages/BatchJobStatusPage'
import Hackathons from './pages/Hackathons'
import OpenSource from './pages/OpenSource'
import AdvocacyTopics from './pages/AdvocacyTopics'
import FactChecking from './pages/FactChecking'
import UnifiedSearch from './pages/UnifiedSearch'
import JurisdictionsSearch from './pages/JurisdictionsSearch'
import PolicyMap from './pages/PolicyMap'
import DecisionsMapPage from './pages/DecisionsMapPage'
import CensusMapPage from './pages/CensusMapPage'
import CensusDrilldownMapPage from './pages/CensusDrilldownMapPage'
import DataExplorerLayout from './components/DataExplorerLayout'
import DataExplorerScorecardPage from './pages/DataExplorerScorecardPage'
import BillDetail from './pages/BillDetail'
import GrantDetail from './pages/GrantDetail'
import DecisionDetail from './pages/DecisionDetail'
import MeetingDetail from './pages/MeetingDetail'
import MeetingDocuments from './pages/MeetingDocuments'
import MeetingCompare from './pages/MeetingCompare'
import EventBillDetail from './pages/EventBillDetail'
import NotFound from './pages/NotFound'
import { DATA_EXPLORER_MAP_BASE } from './utils/dataExplorerPaths'

/** Old route-based drill-down (`/map/state/13/...`, `/map/place/13/...`) is now in-page;
 * redirect those bookmarks to the unified `/map/us/{vintage}/{metric}` entry. */
function LegacyStatePlaceRedirect() {
  const { vintage, metric } = useParams<{ vintage: string; metric: string }>()
  const { search } = useLocation()
  const v = vintage ?? '2024'
  const m = metric ?? 'median_household_income'
  return <Navigate to={`${DATA_EXPLORER_MAP_BASE}/us/${v}/${m}${search}`} replace />
}

/** `/map-v2/...` was the staging URL while the new page lived alongside the old one. */
function MapV2AliasRedirect() {
  const { pathname, search } = useLocation()
  const next = pathname.replace(/^\/data-explorer\/map-v2/, DATA_EXPLORER_MAP_BASE)
  return <Navigate to={`${next}${search}`} replace />
}

/** Old bookmarked URLs used `/census-map/county/...`; national view is now state-level under Data explorer. */
function CensusCountyAliasRedirect() {
  const { vintage, metric } = useParams<{ vintage: string; metric: string }>()
  const { search } = useLocation()
  const v = vintage ?? '2024'
  const m = metric ?? 'median_household_income'
  return <Navigate to={`${DATA_EXPLORER_MAP_BASE}/us/${v}/${m}${search}`} replace />
}

function DataExplorerMapDefaultRedirect() {
  const { data, isError, isPending } = useQuery({
    queryKey: ['data-explorer-map-root-redirect'],
    queryFn: async (): Promise<string> => {
      const rm = await fetch('/data/census-map/manifest.json')
      if (!rm.ok) throw new Error('manifest')
      const manifest = (await rm.json()) as {
        vintage?: string
        vintages?: string[]
        metrics?: { slug: string }[]
      }
      const mv =
        Array.isArray(manifest.vintages) && manifest.vintages.length > 0
          ? manifest.vintages
          : manifest.vintage
            ? [manifest.vintage]
            : []
      let vintages = mv
      const rt = await fetch('/data/census-map/state_trends.json')
      if (rt.ok) {
        const t = (await rt.json()) as { vintages?: string[] }
        if (t.vintages?.length) vintages = t.vintages
      }
      const v = vintages.length ? vintages[vintages.length - 1]! : (manifest.vintage ?? '2024')
      const metric = manifest.metrics?.[0]?.slug ?? 'median_household_income'
      return `${DATA_EXPLORER_MAP_BASE}/us/${v}/${metric}`
    },
  })
  if (isPending) return <div className="p-8 text-slate-600">Loading map…</div>
  if (isError) return <Navigate to={`${DATA_EXPLORER_MAP_BASE}/us/2024/median_household_income`} replace />
  return <Navigate to={data!} replace />
}

/** Rewrites `/census-map/...` bookmarks to `/data-explorer/map/...`. */
function LegacyCensusMapRedirect() {
  const { pathname, search } = useLocation()
  if (pathname === '/census-map' || pathname === '/census-map/') {
    return <DataExplorerMapDefaultRedirect />
  }
  const path = pathname.replace(/^\/census-map/, DATA_EXPLORER_MAP_BASE)
  return <Navigate to={`${path}${search}`} replace />
}

/**
 * Emits a short `route.change` span on every navigation. Rendered inside the
 * Router so `useLocation()` is available. Attribute is the path only (no query
 * string) to keep cardinality bounded and avoid leaking search terms.
 */
function RouteChangeTracer() {
  const location = useLocation()
  useEffect(() => {
    const span = tracer.startSpan('route.change', {
      attributes: { 'route.path': location.pathname },
    })
    span.end()
  }, [location.pathname])
  return null
}

function App() {
  return (
    <>
      <RouteChangeTracer />
      <Routes>
      {/* Ground News-style homepage without Layout (has its own header) */}
      <Route path="/" element={<Home />} />
      
      {/* Old modern home page (if needed) */}
      <Route path="/classic" element={<Layout />}>
        <Route index element={<HomeModern />} />
      </Route>
      
      {/* All other pages with sidebar layout */}
      <Route path="/" element={<Layout />}>
        <Route path="explore" element={<Explore />} />
        <Route path="search" element={<UnifiedSearch />} />
        <Route path="jurisdictions" element={<JurisdictionsSearch />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="people" element={<PeopleFinder />} />
        <Route path="person/:id" element={<PersonDetail />} />
        <Route path="heatmap" element={<Heatmap />} />
        <Route path="policy-map" element={<PolicyMap />} />
        <Route path="decisions-map" element={<DecisionsMapPage />} />
        <Route path="census-map/county/:vintage/:metric" element={<CensusCountyAliasRedirect />} />
        <Route path="census-map/*" element={<LegacyCensusMapRedirect />} />
        <Route path="data-explorer" element={<DataExplorerLayout />}>
          <Route index element={<DataExplorerMapDefaultRedirect />} />
          <Route path="scorecard" element={<DataExplorerScorecardPage />} />
          <Route path="jurisdiction-quality" element={<JurisdictionMappingQualityPage />} />
          <Route path="lighthouse-report" element={<LighthouseReportPage />} />
          <Route path="batch-jobs" element={<BatchJobStatusPage />} />
          <Route path="map/us/:vintage/:metric" element={<CensusDrilldownMapPage />} />
          <Route path="map/state/:stateFips/:vintage/:metric" element={<LegacyStatePlaceRedirect />} />
          <Route path="map/place/:stateFips/:vintage/:metric" element={<LegacyStatePlaceRedirect />} />
          <Route path="map" element={<DataExplorerMapDefaultRedirect />} />
          {/* Legacy staging URLs while the drilldown lived alongside the old page.
              Anyone with a bookmark to /map-v2/... lands on the canonical /map/... now. */}
          <Route path="map-v2/*" element={<MapV2AliasRedirect />} />
          {/* Old CensusMapPage retained at `/map-legacy/...` for one-click rollback if needed. */}
          <Route path="map-legacy/us/:vintage/:metric" element={<CensusMapPage />} />
          <Route path="map-legacy/state/:stateFips/:vintage/:metric" element={<CensusMapPage />} />
          <Route path="map-legacy/place/:stateFips/:vintage/:metric" element={<CensusMapPage />} />
        </Route>
        <Route path="bill/:billId" element={<BillDetail />} />
        <Route path="grants/:id" element={<GrantDetail />} />
        <Route path="decisions/:id" element={<DecisionDetail />} />
        <Route path="meetings/:id" element={<MeetingDetail />} />
        <Route path="jurisdiction/:jurisdictionId/meetings" element={<MeetingDocuments />} />
        <Route
          path="jurisdiction/:jurisdictionId/meetings/:eventMeetingId/compare"
          element={<MeetingCompare />}
        />
        <Route path="bills/:id" element={<EventBillDetail />} />
        <Route path="documents" element={<Documents />} />
        <Route path="opportunities" element={<Opportunities />} />
        <Route path="nonprofits" element={<Nonprofits />} />
        <Route path="nonprofits-hf" element={<NonprofitsHF />} />
        <Route path="debate-grader" element={<DebateFinder />} />
        <Route path="profile" element={<Profile />} />
        <Route path="settings" element={<Settings />} />
        <Route path="events" element={<Events />} />
        <Route path="services" element={<Services />} />
        <Route path="developers" element={<Developers />} />
        <Route
          path="build/jurisdiction-mapping-quality"
          element={<Navigate to="/data-explorer/jurisdiction-quality" replace />}
        />
        <Route path="hackathons" element={<Hackathons />} />
        <Route path="opensource" element={<OpenSource />} />
        <Route path="advocacy-topics" element={<AdvocacyTopics />} />
        <Route path="fact-checking" element={<FactChecking />} />
      </Route>
      
      {/* 404 Page - Catch all unmatched routes */}
      <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  )
}

export default App
