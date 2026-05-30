import HomeExploreQuickNav from './HomeExploreQuickNav'

/**
 * Same left column shell as `/explore`: Quick Navigation cards on a slate panel.
 * Used for Data explorer routes so map/scorecard match the Explore sidebar.
 */
export default function ExploreQuickNavSidebarPanel({
  onNavigate,
  deferSectionNavigationMs,
}: {
  onNavigate?: () => void
  /** When set, section title clicks wait this long before navigating; a second click cancels and expands the row. */
  deferSectionNavigationMs?: number
}) {
  return (
    <div className="flex h-[calc(100dvh-4rem)] min-h-0 flex-col bg-slate-300 px-2 pb-2 pt-3">
      <HomeExploreQuickNav onNavigate={onNavigate} deferSectionNavigationMs={deferSectionNavigationMs} />
    </div>
  )
}
