import HeaderPlaceScope from './HeaderPlaceScope'
import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import { usePlacePick } from '../hooks/usePlacePick'
import { DATABRICKS_APP_URL, DATABRICKS_WORKSPACE_URL } from '../utils/adminPaths'
import { DATA_EXPLORER_MAP_BASE } from '../utils/dataExplorerPaths'
import { DOCS_INTRO } from '../utils/docsLinks'
import { headerPlaceLabel, headerPlaceState, searchForNational } from '../utils/headerPlace'
import { activeNavKey, type NavKey } from '../utils/navActive'
import { SOUND_EVENT, readSoundSetting, writeSoundSetting } from '../utils/stanceSound'
import LocationPickerDialog from './LocationPickerDialog'

const DATA_EXPLORER_ENTRY = `${DATA_EXPLORER_MAP_BASE}/us/2024/median_household_income`
const MOBILE_MENU_ID = 'site-mobile-menu'
/** Below this width the links fold into the menu (the widest place control, "National · Use <town>", + four links + login need ~1024px). */
const MENU_BREAKPOINT = 1024

const menuBtn: CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  background: 'none',
  border: 'none',
  padding: '10px 12px',
  fontSize: 14,
  color: '#44403c',
  cursor: 'pointer',
  fontFamily: 'inherit',
  borderRadius: 8,
  textDecoration: 'none',
  boxSizing: 'border-box',
}

const menuSectionLabel: CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 0.4,
  textTransform: 'uppercase',
  color: '#a8a29e',
  padding: '8px 12px 2px',
  borderTop: '1px solid #f5f5f4',
  marginTop: 4,
}

const TEAL = '#0d9488'
const TEAL_DARK = '#0f766e'
const INK = '#1c1917'

/** Scoped styles for the shared site header (`sh-*`, so the home page's own styles can't reach it). */
const HEADER_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800;900&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
.site-header { font-family: 'Source Sans 3', system-ui, sans-serif; }
.site-header .font-display { font-family: 'Playfair Display', Georgia, serif; }
.site-header .font-mono-x { font-family: 'IBM Plex Mono', monospace; }
.site-header .sh-burger { display: none; }
.site-header .sh-navlink { position: relative; background: none; border: none; padding: 4px 0; font-size: 14.5px; font-weight: 600; color: #44403c; cursor: pointer; font-family: inherit; transition: color .2s ease; white-space: nowrap; }
.site-header .sh-navlink::after { content: ''; position: absolute; left: 0; bottom: -3px; height: 2px; width: 0; background: ${TEAL}; transition: width .25s ease; }
.site-header .sh-navlink:hover { color: ${TEAL_DARK}; }
.site-header .sh-navlink:hover::after { width: 100%; }
.site-header .sh-navlink.active { color: ${TEAL_DARK}; }
.site-header .sh-navlink.active::after { width: 100%; }
.site-header .sh-nav { display: flex; gap: 22px; margin-left: auto; align-items: center; }
.site-header .sh-mnational { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 44px; margin: 6px 0 4px; padding: 10px 14px; border-radius: 12px; border: 1px solid #d6d3d1; background: #fff; color: #44403c; font: inherit; font-size: 15px; font-weight: 600; cursor: pointer; }
.site-header button:focus-visible, .site-header a:focus-visible { outline: 2px solid ${TEAL_DARK}; outline-offset: 2px; }
.site-header .sh-mobile { display: none; }
/* #1331: one segmented [📍 town | National] toggle in the header row, desktop and phone. */
.site-header .sh-ptoggle { display: inline-flex; align-items: stretch; max-width: 100%; border: 1px solid rgba(13,148,136,0.35); border-radius: 999px; overflow: hidden; background: #fff; }
.site-header .sh-ptoggle-btn { display: inline-flex; align-items: center; gap: 4px; min-height: 44px; min-width: 0; padding: 0 10px; border: none; background: none; color: ${TEAL_DARK}; font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.site-header .sh-ptoggle-btn + .sh-ptoggle-btn { border-left: 1px solid rgba(13,148,136,0.35); }
.site-header .sh-ptoggle-btn[aria-pressed="true"] { background: ${TEAL_DARK}; color: #fff; }
.site-header .sh-place-slot { display: flex; min-width: 0; max-width: 320px; }
.site-header .sh-ptoggle-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; max-width: 16em; }
.site-header .sh-ptoggle-caret { font-size: 11px; }
.site-header .sh-ptoggle-btn:focus-visible { outline: 2px solid ${TEAL_DARK}; outline-offset: -4px; }
.site-header .sh-ptoggle-btn[aria-pressed="true"]:focus-visible { outline-color: #fff; }
.site-header .sh-ptoggle-btn:not([aria-pressed="true"]):hover { background: rgba(13,148,136,0.08); }
@media (max-width: 379px) { .site-header .sh-ptoggle-text { max-width: 6.5em; } .site-header .sh-ptoggle-btn { padding: 0 8px; } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes sh-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes sh-drop { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
@media (max-width: ${MENU_BREAKPOINT - 1}px) {
  .site-header .sh-nav { display: none; }
  .site-header .sh-burger { display: grid; margin-left: auto; }
  .site-header .sh-place-slot { margin-left: auto; }
  .site-header .sh-place-slot + .sh-burger { margin-left: 0; }
  .site-header .sh-mobile { display: block; }
  .site-header .sh-inner { padding-left: 16px !important; padding-right: 16px !important; gap: 12px !important; }
}
@media (max-width: 760px) {
  .site-header .sh-brand-sub { display: none; }
}
.site-header .sh-brand-home { display: none; }
/* On a narrow phone the C1 mark stays and the name goes, so the place selector fits beside the menu (#1301). */
@media (max-width: 519px) {
  .site-header .sh-brand-text { display: none; }
  .site-header .sh-brand-home { display: block; font-size: 13px; font-weight: 700; color: ${TEAL_DARK}; line-height: 1; }
  .site-header .sh-inner { gap: 8px !important; }
}
.site-header .sh-backdrop { position: fixed; left: 0; right: 0; bottom: 0; background: rgba(28,25,23,0.45); animation: sh-fade .15s ease; z-index: 1; }
.site-header .sh-panel { position: fixed; left: 0; right: 0; background: #fff; border-bottom: 1px solid #e7e5e4; box-shadow: 0 18px 40px rgba(28,25,23,0.18); overflow-y: auto; overscroll-behavior: contain; padding: 12px 16px 20px; animation: sh-drop .18s ease; z-index: 2; display: flex; flex-direction: column; gap: 4px; text-align: left; box-sizing: border-box; }
.site-header .sh-mitem { display: flex; align-items: center; width: 100%; min-height: 48px; padding: 0 12px; border: none; border-radius: 10px; background: none; font: inherit; font-size: 16px; font-weight: 600; color: #44403c; text-align: left; cursor: pointer; text-decoration: none; box-sizing: border-box; }
.site-header .sh-mitem:hover { background: #f5f5f4; }
.site-header .sh-mitem.active { color: ${TEAL_DARK}; background: rgba(13,148,136,0.08); box-shadow: inset 3px 0 0 ${TEAL}; }
.site-header .sh-mplace { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 48px; padding: 0 14px; border-radius: 12px; border: 1px solid rgba(13,148,136,0.3); background: rgba(13,148,136,0.06); color: ${TEAL_DARK}; font: inherit; font-size: 16px; font-weight: 700; text-align: left; cursor: pointer; box-sizing: border-box; margin-bottom: 6px; }
.site-header .sh-mplace-group { cursor: default; padding: 0 4px 0 14px; }
.site-header .sh-mplace-use { flex: 1; min-width: 0; min-height: 44px; padding: 0 8px; border: none; border-radius: 10px; background: none; color: ${TEAL_DARK}; font: inherit; font-size: 15px; font-weight: 700; text-align: left; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.site-header .sh-mplace-more { min-width: 44px; min-height: 44px; border: none; border-left: 1px solid rgba(13,148,136,0.3); background: none; color: ${TEAL_DARK}; font-size: 13px; cursor: pointer; }
.site-header .sh-mlabel { font-size: 12px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: #a8a29e; padding: 12px 12px 4px; }
.site-header .sh-maccount { margin-top: 8px; padding-top: 8px; border-top: 1px solid #e7e5e4; display: flex; flex-direction: column; gap: 4px; }
.site-header .sh-mlogin { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 48px; border: none; border-radius: 12px; background: ${INK}; color: #fff; font: inherit; font-size: 16px; font-weight: 700; cursor: pointer; text-transform: capitalize; box-sizing: border-box; }
.site-header .sh-mlogin.alt { background: #fff; color: ${INK}; border: 1px solid #d6d3d1; }
`

const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'

/**
 * The single, shared top navigation header used by both the home page and the global Layout (search page and every
 * other route). Edit this one place to change the header everywhere.
 */
export default function SiteHeader() {
  const navigate = useNavigate()
  const location = useLocation()
  const { location: savedLocation } = useLocationContext()
  const pickPlace = usePlacePick()
  const [menuOpen, setMenuOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [menuTop, setMenuTop] = useState(64)
  const headerRef = useRef<HTMLElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  /** Return focus to the menu toggle after the picker opened from the phone menu closes. */
  const pickerFromMenu = useRef(false)
  // Story sound lives here on phones (#1017): the story header drops its sound button below 768px.
  const [soundOn, setSoundOn] = useState(() => readSoundSetting())
  useEffect(() => {
    const on = (e: Event) => setSoundOn(Boolean((e as CustomEvent<boolean>).detail))
    window.addEventListener(SOUND_EVENT, on)
    return () => window.removeEventListener(SOUND_EVENT, on)
  }, [])
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  // Which in-page section is currently active, so its nav link stays highlighted
  // after a click and as the user scrolls through it.
  const [activeSection, setActiveSection] = useState('')
  const { user, isAuthenticated, login, logout, isLoading: authLoading } = useAuth()

  // The place the header names (#1191): the URL's ?state=&city=, else the saved location. Never a hard-coded place.
  // On a scope-aware page it names the page's actual scope (#1205): the URL's place, or National (offering the saved town
  // in one click). On home and other pages it names the reader's town.
  const placeState = headerPlaceState(location.pathname, new URLSearchParams(location.search), savedLocation)
  const placeLabel = headerPlaceLabel(
    placeState.kind === 'scoped' || placeState.kind === 'town' ? placeState.place : placeState.kind === 'national-saved' ? placeState.saved : null,
  )
  const savedLabel = placeState.kind === 'national-saved' ? placeLabel : null
  /** Apply the saved town to this page: writes ?state=&city= through usePlacePick, so label, URL and data move together. */
  const applySavedTown = () => {
    setMenuOpen(false)
    // Home with National chosen (#1285): the place is still in the URL or saved; dropping scope=national brings it back.
    const sp = new URLSearchParams(location.search)
    if (location.pathname === '/' && sp.get('scope') === 'national') {
      sp.delete('scope')
      const qs = sp.toString()
      navigate({ pathname: '/', search: qs ? `?${qs}` : '', hash: location.hash }, { replace: false })
      return
    }
    if (!savedLocation) return
    pickPlace(savedLocation)
  }
  /** One click back to National (#1285): resets the scope in the URL, so the label, the map and the data follow. */
  const nationalSearch = searchForNational(location.pathname, new URLSearchParams(location.search), Boolean(placeLabel))
  const goNational = () => {
    if (!nationalSearch) return
    setMenuOpen(false)
    const qs = nationalSearch.toString()
    navigate({ pathname: location.pathname, search: qs ? `?${qs}` : '', hash: location.hash })
  }

  // ── Phone menu (#1191) ──
  const closeMenu = useCallback((returnFocus: boolean) => {
    setMenuOpen(false)
    if (returnFocus) requestAnimationFrame(() => toggleRef.current?.focus())
  }, [])
  const openMenu = () => {
    setMenuTop(Math.max(0, Math.round(headerRef.current?.getBoundingClientRect().bottom ?? 64)))
    setShowLoginMenu(false)
    setMenuOpen(true)
  }
  // A route change (any link in or out of the menu) closes it; focus goes to the new page, not the toggle.
  useEffect(() => {
    setMenuOpen(false)
    setShowLoginMenu(false)
  }, [location.pathname, location.search])
  // While open: body scroll locked, Escape closes, focus moves in and Tab stays inside (toggle + panel).
  useEffect(() => {
    if (!menuOpen) return
    const body = document.body
    const prevOverflow = body.style.overflow
    body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMenu(true)
    }
    document.addEventListener('keydown', onKey)
    const raf = requestAnimationFrame(() => panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus())
    // Widening past the breakpoint (rotation, desktop resize) folds the menu away.
    const mq = window.matchMedia(`(min-width: ${MENU_BREAKPOINT}px)`)
    const onMq = () => {
      if (mq.matches) setMenuOpen(false)
    }
    mq.addEventListener?.('change', onMq)
    return () => {
      body.style.overflow = prevOverflow
      document.removeEventListener('keydown', onKey)
      cancelAnimationFrame(raf)
      mq.removeEventListener?.('change', onMq)
    }
  }, [menuOpen, closeMenu])
  const trapTab = (e: ReactKeyboardEvent) => {
    if (e.key !== 'Tab' || !menuOpen) return
    const nodes = [toggleRef.current, ...Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].filter(
      (n): n is HTMLElement => Boolean(n),
    )
    if (nodes.length === 0) return
    const first = nodes[0]!
    const last = nodes[nodes.length - 1]!
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  const openPicker = (fromMenu: boolean) => {
    pickerFromMenu.current = fromMenu
    if (fromMenu) setMenuOpen(false)
    setShowLoginMenu(false)
    setPickerOpen(true)
  }
  const closePicker = useCallback(() => {
    setPickerOpen(false)
    if (pickerFromMenu.current) {
      pickerFromMenu.current = false
      requestAnimationFrame(() => toggleRef.current?.focus())
    }
  }, [])

  // Scroll-spy: highlight the nav link for whichever section sits in the middle
  // of the viewport. Only the home page hosts these sections, so clear the
  // active section on every other route.
  useEffect(() => {
    if (location.pathname !== '/') {
      setActiveSection('')
      return
    }
    const ids = ['data-stories', 'search', 'how-it-works', 'impact']
    // The section crossing the middle of the screen is active; between sections (the meetings and maps in the
    // middle of the page) none is, so no tab stays lit over unrelated content.
    const inView = new Set<string>()
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) inView.add(e.target.id)
          else inView.delete(e.target.id)
        })
        setActiveSection(ids.find((id) => inView.has(id)) ?? '')
      },
      { rootMargin: '-50% 0px -50% 0px' },
    )
    // Sections may mount a frame after the header; defer the lookup so we attach.
    const raf = requestAnimationFrame(() => {
      ids.forEach((id) => {
        const el = document.getElementById(id)
        if (el) observer.observe(el)
      })
    })
    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
    }
  }, [location.pathname])

  // The place in the address (?state=&city=) travels with every tab (CLAUDE.md: filters carry over across navigation).
  const carriedQuery = (): string => {
    const here = new URLSearchParams(location.search)
    const q = new URLSearchParams()
    const st = here.get('state')
    if (st) {
      q.set('state', st)
      const c = here.get('city')
      if (c) q.set('city', c)
    }
    return q.toString() ? `?${q}` : ''
  }

  // Data Stories, Search and How It Works are sections of the home page (#975): on home we smooth-scroll to it;
  // elsewhere we route home with a hash so HomeV9's hash-scroll effect lands on the right section.
  const goSection = (id: string) => {
    setActiveSection(id) // keep the clicked link highlighted immediately
    const query = carriedQuery()
    if (location.pathname === '/') {
      // Already home: keep or set the carried place (compared by value, not by encoding), then scroll. The home page
      // doesn't remount on a same-route navigate, so the scroll can't wait for its hash effect.
      const here = new URLSearchParams(location.search)
      const q = new URLSearchParams(query)
      const samePlace = (here.get('state') ?? '') === (q.get('state') ?? '') && (here.get('city') ?? '') === (q.get('city') ?? '')
      if (!samePlace) navigate(`/${query}#${id}`, { replace: true })
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } else {
      navigate(`/${query}#${id}`)
    }
  }

  // Impact moved to the footer's Site links (#1191). Chat & Contact lives in the account menu and the footer (#952).
  const active = activeNavKey(location.pathname, activeSection)
  // Places dropped from the primary nav (#1378); /jurisdictions stays reachable from search and elsewhere.
  const navItems: { key: NavKey; label: string; onClick: () => void }[] = [
    { key: 'stories', label: 'Data Stories', onClick: () => goSection('data-stories') },
    { key: 'search', label: 'Search', onClick: () => goSection('search') },
    { key: 'how', label: 'How It Works', onClick: () => goSection('how-it-works') },
  ]

  const goHome = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    setMenuOpen(false)
    setShowLoginMenu(false)
    setActiveSection('')
    // Home keeps the chosen place (#1341): the mark from a story or Places goes to /?state=&city= (or ?scope=national).
    const onCleanHome = location.pathname === '/' && !location.hash && !location.search
    if (location.pathname !== '/') {
      const carried = carriedQuery()
      const national = new URLSearchParams(location.search).get('scope') === 'national'
      navigate(`/${carried || (national ? '?scope=national' : '')}`)
    } else if (!onCleanHome && location.hash) {
      navigate({ pathname: '/', search: location.search })
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior })
    window.dispatchEvent(new CustomEvent('open-navigator:go-home'))
  }

  const userName = user ? user.full_name || user.username || user.email.split('@')[0] : ''
  const onStory = location.pathname.startsWith('/stories/')

  /** The signed-in account's links, shared by the desktop dropdown and the phone menu. */
  const accountLinks = (itemClass: string | undefined, style: CSSProperties | undefined, done: () => void) =>
    user ? (
      <>
        <button type="button" className={itemClass} style={style} onClick={() => { done(); navigate('/profile') }}>My Profile</button>
        <button type="button" className={itemClass} style={style} onClick={() => { done(); navigate('/settings?section=account&tab=profile') }}>Settings</button>
        <button type="button" className={itemClass} style={style} onClick={() => { done(); navigate('/chat') }}>Chat & Contact</button>
        <a href={DOCS_INTRO} target="_blank" rel="noopener noreferrer" className={itemClass} style={style} onClick={done}>Documentation ↗</a>
        <button type="button" className={itemClass} style={{ ...style, fontWeight: 600, color: TEAL_DARK }} onClick={() => { done(); navigate(DATA_EXPLORER_ENTRY) }}>Data explorer</button>
        {user.is_admin && (
          <>
            {itemClass ? <div className="sh-mlabel">Databricks</div> : <div style={menuSectionLabel}>Databricks</div>}
            <a href={DATABRICKS_WORKSPACE_URL} target="_blank" rel="noopener noreferrer" className={itemClass} style={style} onClick={done}>Workspace ↗</a>
            <a href={DATABRICKS_APP_URL} target="_blank" rel="noopener noreferrer" className={itemClass} style={style} onClick={done}>App ↗</a>
          </>
        )}
        <button type="button" className={itemClass} style={{ ...style, color: '#dc2626', fontWeight: 600 }} onClick={() => { done(); logout() }}>Sign out</button>
      </>
    ) : null
  const providers = ['google', 'facebook', 'github', 'huggingface'] as const
  const providerName = (p: (typeof providers)[number]) => (p === 'huggingface' ? 'HuggingFace' : p)

  return (
    <header ref={headerRef} className="site-header" style={{ position: 'sticky', top: 0, zIndex: 50, background: '#fff', borderBottom: '1px solid #e7e5e4' }} onKeyDown={trapTab}>
      <style>{HEADER_CSS}</style>
      <div className="sh-inner" style={{ maxWidth: 1180, margin: '0 auto', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 20, position: 'relative', background: '#fff', zIndex: 3 }}>
        <Link to="/" onClick={goHome} aria-label="Open Navigator home" data-testid="header-home-link" style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, textDecoration: 'none', color: INK }}>
          <div
            className="font-mono-x"
            aria-hidden="true"
            style={{ width: 38, height: 38, borderRadius: '50%', border: `2.5px solid ${TEAL}`, display: 'grid', placeItems: 'center', fontWeight: 800, color: '#0f766e', fontSize: 15 }}
          >
            C1
          </div>
          <div className="sh-brand-home" aria-hidden="true">Home</div>
          <div className="sh-brand-text">
            <div className="font-display" style={{ fontSize: 19, fontWeight: 700, lineHeight: 1.1 }}>
              Open Navigator
            </div>
            <div className="sh-brand-sub" style={{ fontSize: 11.5, color: '#78716c' }}>
              by CommunityOne
            </div>
          </div>
        </Link>

        {/* Place control (#1191, #1205, #1331): one segmented [📍 town | National] toggle on every width; the active half
            is the page's real scope, the town half opens the shared picker. */}
        <div className="sh-place-slot">
          <HeaderPlaceScope onPickPlace={() => openPicker(false)} />
        </div>
        <button
          ref={toggleRef}
          type="button"
          className="sh-burger"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls={MOBILE_MENU_ID}
          onClick={() => (menuOpen ? closeMenu(true) : openMenu())}
          style={{ width: 44, height: 44, border: '1px solid #e7e5e4', borderRadius: 10, background: '#fff', cursor: 'pointer', placeItems: 'center', fontSize: 18, color: INK }}
        >
          {menuOpen ? '✕' : '☰'}
        </button>

        <nav className="sh-nav" aria-label="Main">
          {navItems.map(({ key, label, onClick }) => (
            <button
              key={key}
              type="button"
              className={'sh-navlink' + (active === key ? ' active' : '')}
              aria-current={active === key ? 'page' : undefined}
              onClick={onClick}
            >
              {label}
            </button>
          ))}

          {/* Register / Login — auth-aware */}
          {authLoading ? (
            <div style={{ width: 34, height: 34, borderRadius: '50%', border: `3px solid #e7e5e4`, borderTopColor: TEAL, animation: 'spin 0.8s linear infinite' }} />
          ) : isAuthenticated && user ? (
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                aria-expanded={showLoginMenu}
                onClick={() => setShowLoginMenu(!showLoginMenu)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: '4px 6px' }}
              >
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name || user.email} referrerPolicy="no-referrer" style={{ width: 34, height: 34, borderRadius: '50%', border: `2px solid ${TEAL}`, objectFit: 'cover' }} />
                ) : (
                  <span style={{ width: 34, height: 34, borderRadius: '50%', background: TEAL, color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 14 }}>
                    {userName.charAt(0).toUpperCase()}
                  </span>
                )}
                <span style={{ fontSize: 14, fontWeight: 600, color: '#44403c' }}>{userName}</span>
              </button>
              {showLoginMenu && (
                <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 220, background: '#fff', border: '1px solid #e7e5e4', borderRadius: 12, boxShadow: '0 16px 32px rgba(28,25,23,0.12)', padding: 6, zIndex: 60 }}>
                  {accountLinks(undefined, menuBtn, () => setShowLoginMenu(false))}
                </div>
              )}
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                aria-expanded={showLoginMenu}
                onClick={() => setShowLoginMenu(!showLoginMenu)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: INK, color: '#fff', border: 'none', borderRadius: 10, padding: '10px 18px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap' }}
              >
                <span>Register/Login</span>
                <span style={{ fontSize: 11 }}>▾</span>
              </button>
              {showLoginMenu && (
                <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 220, background: '#fff', border: '1px solid #e7e5e4', borderRadius: 12, boxShadow: '0 16px 32px rgba(28,25,23,0.12)', padding: 8, zIndex: 60 }}>
                  <button type="button" onClick={() => { setShowLoginMenu(false); navigate('/chat') }} style={menuBtn}>
                    Chat & Contact
                  </button>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#78716c', padding: '8px 8px 8px', borderTop: '1px solid #f5f5f4', marginTop: 4 }}>Sign in with:</div>
                  {providers.map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      onClick={() => { setShowLoginMenu(false); login(provider) }}
                      style={{ ...menuBtn, fontWeight: 600, textTransform: 'capitalize' }}
                    >
                      {providerName(provider)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </nav>
      </div>

      {/* ── Phone menu (#1191): a full-width panel under the header over a dimmed backdrop. ── */}
      {menuOpen && (
        <div className="sh-mobile">
          <div className="sh-backdrop" style={{ top: menuTop }} aria-hidden="true" onClick={() => closeMenu(true)} />
          <div
            ref={panelRef}
            id={MOBILE_MENU_ID}
            className="sh-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Site menu"
            style={{ top: menuTop, maxHeight: `calc(100dvh - ${menuTop}px)` }}
          >
            {placeState.kind === 'national-saved' || placeState.kind === 'national' ? (
              <div className="sh-mplace sh-mplace-group" role="group" aria-label="Place for this page">
                <span aria-hidden="true">📍</span>
                <span style={{ flexShrink: 0 }}>National ·</span>
                {savedLabel ? (
                  <button type="button" className="sh-mplace-use" onClick={applySavedTown}>
                    Use {savedLabel}
                  </button>
                ) : (
                  <button type="button" className="sh-mplace-use" aria-haspopup="dialog" onClick={() => openPicker(true)}>
                    Find your town
                  </button>
                )}
                <button type="button" className="sh-mplace-more" aria-haspopup="dialog" aria-label="Pick a town" onClick={() => openPicker(true)}>
                  ▾
                </button>
              </div>
            ) : (
              <button type="button" className="sh-mplace" aria-haspopup="dialog" onClick={() => openPicker(true)}>
                <span aria-hidden="true">📍</span>
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {placeLabel ?? 'Find your town'}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{placeLabel ? 'Change' : 'Set'}</span>
              </button>
            )}
            {nationalSearch && (
              <button type="button" className="sh-mnational" onClick={goNational}>
                <span aria-hidden="true">×</span> Show National
              </button>
            )}

            <nav aria-label="Main" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <button
                type="button"
                className={'sh-mitem' + (location.pathname === '/' && !active ? ' active' : '')}
                data-testid="menu-home"
                onClick={(e) => goHome(e as unknown as MouseEvent<HTMLAnchorElement>)}
              >
                <span aria-hidden="true" style={{ marginRight: 8 }}>🏠</span> Home
              </button>
              {navItems.map(({ key, label, onClick }) => (
                <button
                  key={key}
                  type="button"
                  className={'sh-mitem' + (active === key ? ' active' : '')}
                  aria-current={active === key ? 'page' : undefined}
                  onClick={() => {
                    closeMenu(false)
                    onClick()
                  }}
                >
                  {label}
                </button>
              ))}
              {/* On a story: the sound setting (#1017). */}
              {onStory && (
                <button type="button" className="sh-mitem" aria-pressed={soundOn} onClick={() => writeSoundSetting(!soundOn)}>
                  Story sound: {soundOn ? 'On' : 'Off'}
                </button>
              )}
            </nav>

            <div className="sh-maccount">
              {authLoading ? null : isAuthenticated && user ? (
                <>
                  <div className="sh-mlabel">Signed in as {userName}</div>
                  {accountLinks('sh-mitem', undefined, () => closeMenu(false))}
                </>
              ) : (
                <>
                  <button type="button" className="sh-mitem" onClick={() => { closeMenu(false); navigate('/chat') }}>
                    Chat & Contact
                  </button>
                  {/* One full-width Register / Login; the providers open under it, so the panel stays short. */}
                  <button
                    type="button"
                    className="sh-mlogin"
                    aria-expanded={showLoginMenu}
                    aria-controls="site-mobile-login"
                    onClick={() => setShowLoginMenu(!showLoginMenu)}
                  >
                    Register / Login <span aria-hidden="true" style={{ marginLeft: 8, fontSize: 12 }}>{showLoginMenu ? '▴' : '▾'}</span>
                  </button>
                  {showLoginMenu && (
                    <div id="site-mobile-login" style={{ display: 'grid', gap: 8, marginTop: 4 }}>
                      <div className="sh-mlabel" style={{ paddingTop: 4 }}>Sign in with</div>
                      {providers.map((provider) => (
                        <button
                          key={provider}
                          type="button"
                          className="sh-mlogin alt"
                          onClick={() => { closeMenu(false); login(provider) }}
                        >
                          {providerName(provider)}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <LocationPickerDialog open={pickerOpen} onClose={closePicker} current={placeLabel} onPicked={pickPlace} />
    </header>
  )
}
