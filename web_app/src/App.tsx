import { lazy, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Route, Routes, Navigate, useParams, useLocation, useSearchParams } from 'react-router-dom'
import { tracer } from './instrumentation'
import Layout from './components/Layout'
import SkipLink from './components/SkipLink'
import ScrollToTop from './components/ScrollToTop'
import Home from './pages/Home'
import HomeV9 from './pages/HomeV9'
import PolicyQuestionsPage from './pages/PolicyQuestionsPage'
import PolicyQuestionPage from './pages/PolicyQuestionPage'
import BrowseTopics from './pages/BrowseTopics'
import BrowseCauses from './pages/BrowseCauses'
import DataCenters from './pages/DataCenters'
import MoneyTalk from './pages/MoneyTalk'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import Heatmap from './pages/Heatmap'
import Documents from './pages/Documents'
import Opportunities from './pages/Opportunities'
import Nonprofits from './pages/Nonprofits'
import Efile990Viewer from './pages/Efile990Viewer'
import NonprofitsHF from './pages/NonprofitsHF'
import Settings from './pages/Settings'
import PeopleFinder from './pages/PeopleFinder'
import PersonDetail from './pages/PersonDetail'
import DebateFinder from './pages/DebateGrader'
import Profile from './pages/Profile'
import FeedSetup from './pages/FeedSetup'
import Explore from './pages/Explore'
import Events from './pages/Events'
import Services from './pages/Services'
import Developers from './pages/Developers'
import Support from './pages/Support'
import JurisdictionMappingQualityPage from './pages/JurisdictionMappingQualityPage'
import LighthouseReportPage from './pages/LighthouseReportPage'
import BatchJobStatusPage from './pages/BatchJobStatusPage'
import BatchFailureReasonsPage from './pages/BatchFailureReasonsPage'
import ApplicationLinksAdminPage from './pages/ApplicationLinksAdminPage'
import MeetingKindsAdminPage from './pages/MeetingKindsAdminPage'
import Hackathons from './pages/Hackathons'
import OpenSource from './pages/OpenSource'
import AdvocacyTopics from './pages/AdvocacyTopics'
import FactChecking from './pages/FactChecking'
import UnifiedSearch from './pages/UnifiedSearch'
import MeetingChat from './pages/MeetingChat'
import JurisdictionsSearch from './pages/JurisdictionsSearch'
import PolicyMap from './pages/PolicyMap'
import DecisionsMapPage from './pages/DecisionsMapPage'
import CensusMapPage from './pages/CensusMapPage'
import CensusDrilldownMapPage from './pages/CensusDrilldownMapPage'
import DataExplorerLayout from './components/DataExplorerLayout'
import AdminLayout from './components/AdminLayout'
import DataExplorerScorecardPage from './pages/DataExplorerScorecardPage'
import LazyRouteBoundary from './components/LazyRouteBoundary'
import BillDetail from './pages/BillDetail'
import GrantDetail from './pages/GrantDetail'
import DecisionDetail from './pages/DecisionDetail'
import MeetingDetail from './pages/MeetingDetail'
import BodyDetail from './pages/BodyDetail'
import MeetingDocuments from './pages/MeetingDocuments'
import MeetingCompare from './pages/MeetingCompare'
import EventBillDetail from './pages/EventBillDetail'
import NotFound from './pages/NotFound'
import { DATA_EXPLORER_MAP_BASE } from './utils/dataExplorerPaths'
import { storyRoute } from './utils/topicStories'
import { recordLocation } from './lib/pageClose'
import { STORIES } from './utils/dataStory'
import { useTopicStories } from './hooks/useTopicStories'
import { useDocumentTitle } from './utils/useDocumentTitle'
import { stateName, storyPageTitle } from './utils/routeMeta'
import RouteMetaSync from './components/RouteMetaSync'
import { BoxFlightProvider } from './components/stance/BoxFlightProvider'

// Loaded only when its route is visited (#856): its fonts and chart code stay out of the main bundle, and a
// failure to load it cannot blank the rest of the site.
const DataExplorerMatrixPage = lazy(() => import('./pages/DataExplorerMatrixPage'))

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
  // The trail lets Close (#1405) know the page before this one.
  recordLocation({ pathname: location.pathname, search: location.search })
  useEffect(() => {
    const span = tracer.startSpan('route.change', {
      attributes: { 'route.path': location.pathname },
    })
    span.end()
  }, [location.pathname])
  return null
}

// The challenge and the story pull in gsap and lenis, so they load on their own route chunks and no other page pays for them.
const DataStory = lazy(() => import('./pages/DataStory'))
const TopicStory = lazy(() => import('./pages/TopicStory'))
const BrowseAllTopics = lazy(() => import('./pages/BrowseAllTopics'))
const WhereTownsStand = lazy(() => import('./pages/WhereTownsStand'))
const OrganizationPage = lazy(() => import('./pages/OrganizationPage'))
const DataStories = lazy(() => import('./pages/DataStories'))

/**
 * The Data Center Challenge is retired (#981): its statements are asked in the story itself. `/challenge`,
 * `/challenge/:packId`, `/play` and `/play/:packId` go to the story for that topic, keeping the place in the URL.
 */
function ChallengeRedirect({ to = 'data-centers' }: { to?: string }) {
  const { search } = useLocation()
  return <Navigate to={`/stories/${to}${search}`} replace />
}

function PlayPackRedirect() {
  const { packId = 'data-centers' } = useParams()
  return <ChallengeRedirect to={encodeURIComponent(packId)} />
}

/** `/stories/:storyId` (#1133): the registry's stories (data centers) on DataStory, topic slugs on TopicStory. */
function StoryRoute() {
  const { storyId = '' } = useParams()
  // The tab names the story's topic (#1191): the registry's topic, else the curated topic's name from the catalog.
  const { stories } = useTopicStories()
  const [params] = useSearchParams()
  const reg = STORIES[storyId]
  const topic = reg ? reg.topic : stories[storyId]?.title
  // The same title the server sends in the page's HTML (#1430): "Gun control in Alabama — Data story".
  useDocumentTitle(topic ? storyPageTitle(topic, stateName(params.get('state'))) : 'Data story')
  return storyRoute(storyId) === 'data' ? <DataStory /> : <TopicStory slug={storyId} />
}

function App() {
  return (
    <>
      <SkipLink />
      <ScrollToTop />
      <RouteChangeTracer />
      <RouteMetaSync />
      <BoxFlightProvider>
      <Routes>
      {/* v9 prototype homepage (single-column; has its own header) */}
      <Route path="/" element={<HomeV9 />} />
      {/* Previous homepage, kept reachable for comparison/rollback */}
      <Route path="/home-original" element={<Home />} />

      {/* All other pages with sidebar layout */}
      <Route path="/" element={<Layout />}>
        <Route path="explore" element={<Explore />} />
        <Route path="search" element={<UnifiedSearch />} />
        <Route path="chat" element={<MeetingChat />} />
        <Route path="jurisdictions" element={<JurisdictionsSearch />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="people" element={<PeopleFinder />} />
        <Route path="person/:id" element={<PersonDetail />} />
        <Route path="heatmap" element={<Heatmap />} />
        <Route path="policy-map" element={<PolicyMap />} />
        <Route path="decisions-map" element={<DecisionsMapPage />} />
        <Route path="policy-questions" element={<PolicyQuestionsPage />} />
        <Route path="policy-question/:questionId" element={<PolicyQuestionPage />} />
        <Route path="browse-topics" element={<BrowseTopics />} />
        {/* Every main topic, last year against this year, in one animated dumbbell (#1343). */}
        <Route
          path="browse-topics/all"
          element={
            <LazyRouteBoundary name="Browse all topics">
              <BrowseAllTopics />
            </LazyRouteBoundary>
          }
        />
        {/* Where towns stand: per place and topic, how public speakers leaned (#1438). */}
        <Route
          path="where-towns-stand"
          element={
            <LazyRouteBoundary name="Where towns stand">
              <WhereTownsStand />
            </LazyRouteBoundary>
          }
        />
        <Route path="browse-causes" element={<BrowseCauses />} />
        <Route path="data-centers" element={<DataCenters />} />
        <Route path="play" element={<ChallengeRedirect />} />
        <Route path="play/:packId" element={<PlayPackRedirect />} />
        <Route path="challenge" element={<ChallengeRedirect />} />
        <Route path="challenge/:packId" element={<PlayPackRedirect />} />
        <Route
          path="stories"
          element={
            <LazyRouteBoundary name="Data stories">
              <DataStories />
            </LazyRouteBoundary>
          }
        />
        {/* One route for every story (#1133): the registry's stories on DataStory, any curated topic on TopicStory. */}
        <Route
          path="stories/:storyId"
          element={
            <LazyRouteBoundary name="Data story">
              <StoryRoute />
            </LazyRouteBoundary>
          }
        />
        {/* Organization page (#1015). */}
        <Route
          path="organizations/:masterOrgId"
          element={
            <LazyRouteBoundary name="Organization">
              <OrganizationPage />
            </LazyRouteBoundary>
          }
        />
        <Route path="money-and-talk" element={<MoneyTalk />} />
        <Route path="census-map/county/:vintage/:metric" element={<CensusCountyAliasRedirect />} />
        <Route path="census-map/*" element={<LegacyCensusMapRedirect />} />
        <Route path="data-explorer" element={<DataExplorerLayout />}>
          <Route index element={<DataExplorerMapDefaultRedirect />} />
          <Route path="scorecard" element={<DataExplorerScorecardPage />} />
          <Route
            path="matrix"
            element={
              <LazyRouteBoundary name="How states compare">
                <DataExplorerMatrixPage />
              </LazyRouteBoundary>
            }
          />
          <Route path="jurisdiction-quality" element={<JurisdictionMappingQualityPage />} />
          {/* Lighthouse report + batch jobs moved to the Admin area; keep old URLs working. */}
          <Route path="lighthouse-report" element={<Navigate to="/admin/lighthouse-report" replace />} />
          <Route path="batch-jobs" element={<Navigate to="/admin/batch-jobs" replace />} />
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
        {/* Admin area — operational tools, reachable from the logged-in profile menu. */}
        <Route path="admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/batch-jobs" replace />} />
          <Route path="lighthouse-report" element={<LighthouseReportPage />} />
          <Route path="batch-jobs" element={<BatchJobStatusPage />} />
          <Route path="batch-jobs/failures" element={<BatchFailureReasonsPage />} />
          <Route path="application-links" element={<ApplicationLinksAdminPage />} />
          <Route path="meeting-kinds" element={<MeetingKindsAdminPage />} />
        </Route>
        <Route path="bill/:billId" element={<BillDetail />} />
        <Route path="grants/:id" element={<GrantDetail />} />
        <Route path="efile990" element={<Efile990Viewer />} />
        <Route path="efile990/:objectId" element={<Efile990Viewer />} />
        <Route path="decisions/:id" element={<DecisionDetail />} />
        <Route path="meetings/:id" element={<MeetingDetail />} />
        <Route path="bodies/:bodyId" element={<BodyDetail />} />
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
        <Route path="feed-setup" element={<FeedSetup />} />
        <Route path="settings" element={<Settings />} />
        <Route path="events" element={<Events />} />
        <Route path="services" element={<Services />} />
        <Route path="developers" element={<Developers />} />
        <Route path="support" element={<Support />} />
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
      </BoxFlightProvider>
    </>
  )
}

export default App
