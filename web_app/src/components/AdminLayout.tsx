import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
  ADMIN_APPLICATION_LINKS,
  ADMIN_BATCH_JOBS,
  ADMIN_LIGHTHOUSE_REPORT,
  ADMIN_MEETING_KINDS,
} from '../utils/adminPaths'
import { adminGuideHref } from '../utils/docsLinks'

function tabCls({ isActive }: { isActive: boolean }) {
  return [
    'inline-flex items-center gap-1.5 border-b-2 px-2.5 py-1.5 text-sm font-medium transition-colors',
    isActive
      ? 'border-teal-600 text-teal-800'
      : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900',
  ].join(' ')
}

export default function AdminLayout() {
  const { pathname } = useLocation()
  const { user, isLoading } = useAuth()

  // Admin-only area: wait for auth to resolve, then bounce non-admins home so
  // the route can't be reached by typing the URL even though the menu link is
  // hidden. This is a UX gate, not a security boundary — the underlying
  // lighthouse/batch-job data endpoints are not yet auth-protected.
  if (isLoading) {
    return (
      <div className="flex min-h-[calc(100dvh-4.25rem)] flex-1 items-center justify-center page-bg text-sm text-slate-600">
        Loading…
      </div>
    )
  }
  if (!user?.is_admin) {
    return <Navigate to="/" replace />
  }
  const onLighthouseReport =
    pathname === ADMIN_LIGHTHOUSE_REPORT || pathname.startsWith(`${ADMIN_LIGHTHOUSE_REPORT}/`)
  const onBatchJobs = pathname === ADMIN_BATCH_JOBS || pathname.startsWith(`${ADMIN_BATCH_JOBS}/`)
  const onApplicationLinks = pathname === ADMIN_APPLICATION_LINKS
  const onMeetingKinds =
    pathname === ADMIN_MEETING_KINDS || pathname.startsWith(`${ADMIN_MEETING_KINDS}/`)
  const guideHref = adminGuideHref(pathname)

  return (
    <div className="flex min-h-[calc(100dvh-4.25rem)] flex-1 flex-col page-bg">
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 min-h-0 flex-col px-3 py-2 sm:px-4 md:px-5 md:py-3">
        <header className="shrink-0 rounded-lg border border-slate-300/80 bg-white px-3 py-2 shadow-sm sm:px-4 sm:py-2">
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-lg font-semibold leading-tight text-slate-900 sm:text-xl">
              Admin
            </h1>
            {guideHref ? (
              <a
                href={guideHref}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-sm font-medium text-teal-800 hover:underline"
              >
                Guide ↗
              </a>
            ) : null}
          </div>
          <p className="mt-0.5 max-w-[52rem] text-[11px] leading-snug text-slate-600 sm:text-xs">
            Operational tooling — live batch-job progress for the caption / analyze pipelines, meeting-kind
            review, application links, and data-quality Lighthouse scores.
          </p>
          <nav
            className="mt-1.5 -mx-1 flex gap-1 overflow-x-auto px-1 pb-0.5 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
            aria-label="Admin views"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            <NavLink
              to={ADMIN_BATCH_JOBS}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Batch jobs
            </NavLink>
            <NavLink
              to={ADMIN_MEETING_KINDS}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Meeting kinds
            </NavLink>
            <NavLink
              to={ADMIN_APPLICATION_LINKS}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Application links
            </NavLink>
            <NavLink
              to={ADMIN_LIGHTHOUSE_REPORT}
              end
              className={({ isActive }) => `${tabCls({ isActive })} shrink-0 whitespace-nowrap`}
            >
              Lighthouse report
            </NavLink>
          </nav>
          {onApplicationLinks && (
            <p className="mt-0.5 text-[10px] leading-snug text-slate-600 sm:text-[11px]" aria-live="polite">
              Job-application links for data center projects (`public.job_application_link`). Links not
              verified in 30 days are flagged Stale on the public page.
            </p>
          )}
          {onMeetingKinds && (
            <p className="mt-0.5 text-[10px] leading-snug text-slate-600 sm:text-[11px]" aria-live="polite">
              Troubleshoot Jev not_government screens: sort by probability and override false labels
              (`bronze.bronze_video_meeting_kind_override`).
            </p>
          )}
          {(onLighthouseReport || onBatchJobs) && (
            <p className="mt-0.5 text-[10px] leading-snug text-slate-600 sm:text-[11px]" aria-live="polite">
              {onLighthouseReport
                ? 'Scores and warnings are read from the latest `bronze.bronze_jurisdiction_website_lighthouse` row for the URL you enter (after accessibility lighthouse ingest).'
                : 'Live caption/analyze batch progress from Postgres (`bronze.youtube_batch_job_runs`) via SSE. Click a jurisdiction for per-video outcomes.'}
            </p>
          )}
        </header>

        {/* Workspace: mid-slate so white cards read clearly. */}
        <div className="mt-2 min-h-0 min-w-0 flex-1 rounded-xl border border-stone-300 bg-stone-200/50 p-1.5 shadow-inner sm:mt-2 sm:p-2 md:p-2.5">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
