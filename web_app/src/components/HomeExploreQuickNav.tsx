import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import { homeExploreSectionHash, type HomeQuickNavGroupId } from '../data/exploreActionPhases'
import {
  flyoutIcons,
  homeQuickNavFlyoutItems,
  resolveHomeFlyoutHref,
  type HomeFlyoutItem,
} from '../data/homeQuickNavFlyouts'

const T = {
  tealDark: '#1b3c39',
  tealMid: '#2d6b65',
  tealLight: '#4a9e96',
  tealPale: '#e6f3f2',
  accent: '#f0a500',
  accentPale: '#fff4d6',
  white: '#ffffff',
  textDark: '#1a2e2d',
  textMid: '#4a6665',
  textLight: '#8aabaa',
  border: '#ddecea',
} as const

/** Outline nav icons (reference: light gray idle, white on teal hover) */
function NavIcon({ children, stroke }: { children: ReactNode; stroke: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  )
}

const NAV_ROW_ICONS: Record<HomeQuickNavGroupId, (stroke: string) => ReactNode> = {
  cause: (stroke) => (
    <NavIcon stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </NavIcon>
  ),
  plan: (stroke) => (
    <NavIcon stroke={stroke}>
      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.568.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
    </NavIcon>
  ),
  find: (stroke) => (
    <NavIcon stroke={stroke}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </NavIcon>
  ),
  track: (stroke) => (
    <NavIcon stroke={stroke}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </NavIcon>
  ),
  build: (stroke) => (
    <NavIcon stroke={stroke}>
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </NavIcon>
  ),
}

const MARKETING_ROWS: { id: HomeQuickNavGroupId; label: string; sub: string }[] = [
  { id: 'cause', label: 'Choose a Cause', sub: 'Pick what matters to you first' },
  { id: 'plan', label: 'Make a Plan', sub: 'Personal and community paths, allies, and outcomes' },
  { id: 'find', label: 'Find Help', sub: 'Nonprofits, programs, and family supports' },
  { id: 'track', label: 'Track Decisions', sub: 'Meetings, budgets, maps, and verification' },
  { id: 'build', label: 'Build With Data', sub: 'Open datasets & API' },
]

/** Drill-down links: compact rows with a light motion on hover. */
function DrilldownLinkRow({ item, onPick, styleDelay }: { item: HomeFlyoutItem; onPick: () => void; styleDelay: number }) {
  const href = resolveHomeFlyoutHref(item.to)
  const icon = flyoutIcons[item.iconKey]('currentColor')
  const className =
    'group/drill flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm font-medium text-slate-800 transition-[background-color,transform,box-shadow] duration-200 hover:bg-white hover:shadow-sm hover:ring-1 hover:ring-slate-200/80 active:scale-[0.99]'
  const iconWrap = (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center text-slate-500 transition-transform duration-200 group-hover/drill:scale-105 [&>svg]:block">
      {icon}
    </span>
  )
  const label = <span className="min-w-0 flex-1 leading-snug">{item.label}</span>

  const motionStyle = { transitionDelay: `${styleDelay}ms` } as const

  if (item.external) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        style={motionStyle}
        onClick={onPick}
      >
        {iconWrap}
        {label}
      </a>
    )
  }

  return (
    <Link to={href} className={className} style={motionStyle} onClick={onPick}>
      {iconWrap}
      {label}
    </Link>
  )
}

type HomeExploreQuickNavProps = {
  /** e.g. close app layout mobile drawer after following a link */
  onNavigate?: () => void
  /**
   * When > 0, clicking a section title waits this many ms before navigating to Explore.
   * A second click while waiting cancels navigation and toggles the shortcut panel (same as the chevron).
   * Use on Data explorer (and similar) so two quick taps expand without leaving the page first.
   */
  deferSectionNavigationMs?: number
}

export default function HomeExploreQuickNav({
  onNavigate,
  deferSectionNavigationMs = 0,
}: HomeExploreQuickNavProps) {
  const navigate = useNavigate()
  const [expandedId, setExpandedId] = useState<HomeQuickNavGroupId | null>(null)
  const pendingSectionNavRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(
    () => () => {
      if (pendingSectionNavRef.current) clearTimeout(pendingSectionNavRef.current)
    },
    [],
  )

  const closePanels = () => {
    setExpandedId(null)
    onNavigate?.()
  }

  function toggleExpanded(id: HomeQuickNavGroupId) {
    setExpandedId((cur) => (cur === id ? null : id))
  }

  function handleSectionTitleClick(rowId: HomeQuickNavGroupId, exploreHref: string, e: MouseEvent<HTMLAnchorElement>) {
    if (deferSectionNavigationMs <= 0) {
      closePanels()
      return
    }
    e.preventDefault()
    if (pendingSectionNavRef.current != null) {
      clearTimeout(pendingSectionNavRef.current)
      pendingSectionNavRef.current = null
      toggleExpanded(rowId)
      return
    }
    pendingSectionNavRef.current = setTimeout(() => {
      pendingSectionNavRef.current = null
      closePanels()
      navigate(exploreHref)
    }, deferSectionNavigationMs)
  }

  return (
    <div className="relative isolate flex h-full min-h-0 max-h-full w-full flex-col overflow-x-hidden overflow-y-hidden rounded-2xl border border-slate-200/90 bg-white p-3 shadow-[0_8px_32px_-8px_rgba(15,23,42,0.14)] ring-1 ring-slate-900/[0.06]">
      <h3
        className="mb-2 shrink-0 text-base font-bold text-slate-900"
        style={{ fontFamily: "'DM Sans',sans-serif" }}
      >
        Quick Navigation
      </h3>

      <nav
        className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain pr-0.5"
        aria-label="Quick navigation and explore paths"
      >
        {MARKETING_ROWS.map((row) => {
          const items = homeQuickNavFlyoutItems(row.id)
          const exploreHref = `/explore#${homeExploreSectionHash(row.id)}`
          const isOpen = expandedId === row.id
          const panelId = `quick-nav-panel-${row.id}`
          const triggerId = `quick-nav-trigger-${row.id}`

          return (
            <div
              key={row.id}
              data-home-nav-row={row.id}
              className={`overflow-hidden rounded-xl border transition-[border-color,box-shadow,background] duration-300 ease-out ${
                isOpen
                  ? 'border-teal-200/90 bg-gradient-to-b from-white via-teal-50/40 to-teal-50/[0.55] shadow-[0_6px_20px_-6px_rgba(15,118,110,0.22)] ring-1 ring-teal-900/[0.07]'
                  : 'border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04] hover:border-slate-300/90 hover:shadow'
              }`}
            >
              <div className="flex min-h-[3.25rem] items-stretch">
                <Link
                  to={exploreHref}
                  onClick={(e) => handleSectionTitleClick(row.id, exploreHref, e)}
                  className={`mx-0 flex min-w-0 flex-1 cursor-pointer items-center gap-2 px-2 py-1.5 transition-[background-color,color] duration-200 sm:px-2.5 ${
                    isOpen ? 'bg-transparent' : 'hover:bg-slate-50/90'
                  }`}
                  style={{
                    borderLeftWidth: 3,
                    borderLeftStyle: 'solid',
                    borderLeftColor: isOpen ? T.accent : 'transparent',
                  }}
                  id={`quick-nav-heading-${row.id}`}
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center" aria-hidden>
                    {NAV_ROW_ICONS[row.id](isOpen ? T.tealMid : '#94a3b8')}
                  </span>
                  <div className="min-w-0 flex-1 py-0.5">
                    <div
                      className="text-[13px] font-semibold leading-tight transition-colors duration-200"
                      style={{
                        color: isOpen ? T.tealDark : T.textDark,
                        fontFamily: "'DM Sans',sans-serif",
                      }}
                    >
                      {row.label}
                    </div>
                    <div
                      className="text-[10px] leading-snug transition-colors duration-200"
                      style={{
                        color: T.textMid,
                        fontFamily: "'DM Sans',sans-serif",
                      }}
                    >
                      {row.sub}
                    </div>
                  </div>
                </Link>
                <button
                  type="button"
                  id={triggerId}
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  className={`flex w-11 shrink-0 flex-col items-center justify-center border-l transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-500/50 ${
                    isOpen
                      ? 'border-teal-200/70 bg-teal-50/50 text-teal-800'
                      : 'border-slate-100 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600'
                  }`}
                  title={isOpen ? 'Hide shortcuts' : 'Show shortcuts'}
                  onClick={(e) => {
                    e.preventDefault()
                    toggleExpanded(row.id)
                  }}
                >
                  <ChevronDownIcon
                    className={`h-5 w-5 transition-transform duration-300 ease-out ${isOpen ? '-rotate-180' : 'rotate-0'}`}
                    aria-hidden
                  />
                  <span className="sr-only">
                    {isOpen ? `Collapse shortcuts for ${row.label}` : `Expand shortcuts for ${row.label}`}
                  </span>
                </button>
              </div>

              <div
                id={panelId}
                role="region"
                aria-labelledby={`quick-nav-heading-${row.id}`}
                className={`grid transition-[grid-template-rows] duration-300 ease-[cubic-bezier(0.33,1,0.68,1)] motion-reduce:transition-none ${
                  isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                }`}
              >
                <div className="min-h-0 overflow-hidden">
                  <div
                    aria-hidden={!isOpen}
                    className={`border-t px-1.5 pb-2 pt-1.5 ${isOpen ? 'border-teal-100/80' : 'border-transparent'}`}
                  >
                    <p
                      className="px-1.5 pb-1 pt-0.5 text-[10px] font-semibold uppercase tracking-wider text-teal-800/80"
                      style={{ fontFamily: "'DM Sans',sans-serif" }}
                    >
                      {row.label}
                    </p>
                    <div className="flex flex-col gap-0.5 rounded-lg bg-white/60 p-1 ring-1 ring-teal-900/[0.04] backdrop-blur-[2px]">
                      {items.map((item, i) => (
                        <DrilldownLinkRow key={item.id} item={item} onPick={closePanels} styleDelay={isOpen ? Math.min(i * 35, 200) : 0} />
                      ))}
                    </div>
                    <Link
                      to={exploreHref}
                      onClick={closePanels}
                      className="mt-1.5 block rounded-md px-2 py-1.5 text-xs font-semibold text-teal-800/90 transition-colors hover:bg-teal-100/50 hover:text-teal-950"
                    >
                      Open Explore: {row.label} →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </nav>
    </div>
  )
}
