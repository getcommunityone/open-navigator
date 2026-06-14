import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { DATABRICKS_APP_URL, DATABRICKS_WORKSPACE_URL } from '../utils/adminPaths'

const TEAL = '#0d9488'
const TEAL_DARK = '#0f766e'
const INK = '#1c1917'

/** Scoped styles for the shared site header. Kept self-contained (scoped under
 * `.site-header`) so the header renders identically whether it sits inside the
 * home page's `.v9` wrapper or the global Layout. */
const HEADER_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800;900&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
.site-header { font-family: 'Source Sans 3', system-ui, sans-serif; }
.site-header .font-display { font-family: 'Playfair Display', Georgia, serif; }
.site-header .font-mono-x { font-family: 'IBM Plex Mono', monospace; }
.site-header .v9-burger { display: none; }
.site-header .v9-navlink { position: relative; background: none; border: none; padding: 4px 0; font-size: 14.5px; font-weight: 600; color: #44403c; cursor: pointer; font-family: inherit; transition: color .2s ease; }
.site-header .v9-navlink::after { content: ''; position: absolute; left: 0; bottom: -3px; height: 2px; width: 0; background: ${TEAL}; transition: width .25s ease; }
.site-header .v9-navlink:hover { color: ${TEAL_DARK}; }
.site-header .v9-navlink:hover::after { width: 100%; }
.site-header .v9-navlink.active { color: ${TEAL_DARK}; }
.site-header .v9-navlink.active::after { width: 100%; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) {
  .site-header .v9-nav { display: none; }
  .site-header .v9-nav.open { display: flex; flex-direction: column; align-items: stretch; position: absolute; top: 100%; left: 0; right: 0; background: #fff; border-bottom: 1px solid #e7e5e4; padding: 10px 16px 16px; gap: 4px; box-shadow: 0 16px 32px rgba(28,25,23,0.1); }
  .site-header .v9-burger { display: grid; margin-left: auto; }
  .site-header .v9-brand-sub { display: none; }
}
`

/**
 * The single, shared top navigation header used by both the home page and the
 * global Layout (search page and every other route). Edit this one place to
 * change the header everywhere.
 */
export default function SiteHeader() {
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  // Which in-page section is currently active, so its nav link stays highlighted
  // after a click and as the user scrolls through it.
  const [activeSection, setActiveSection] = useState('')
  const { user, isAuthenticated, login, logout, isLoading: authLoading } = useAuth()

  // Scroll-spy: highlight the nav link for whichever section sits in the middle
  // of the viewport. Only the home page hosts these sections, so clear the
  // active section on every other route.
  useEffect(() => {
    if (location.pathname !== '/') {
      setActiveSection('')
      return
    }
    const ids = ['how-it-works', 'impact']
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActiveSection(e.target.id)
        })
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

  // "How It Works" / "Impact" are in-page sections that only exist on the home
  // page. On home we smooth-scroll to them; elsewhere we route home with a hash
  // so HomeV9's hash-scroll effect lands on the right section.
  const goSection = (id: string) => {
    setActiveSection(id) // keep the clicked link highlighted immediately
    if (location.pathname === '/') {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else {
      navigate(`/#${id}`)
    }
  }

  const navItems: { label: string; onClick: () => void; active: boolean }[] = [
    { label: 'Search', onClick: () => navigate('/search'), active: location.pathname === '/search' },
    { label: 'How It Works', onClick: () => goSection('how-it-works'), active: location.pathname === '/' && activeSection === 'how-it-works' },
    { label: 'Impact', onClick: () => goSection('impact'), active: location.pathname === '/' && activeSection === 'impact' },
    { label: 'Contact', onClick: () => navigate('/support'), active: location.pathname === '/support' },
  ]

  return (
    <header className="site-header" style={{ position: 'sticky', top: 0, zIndex: 50, background: '#fff', borderBottom: '1px solid #e7e5e4' }}>
      <style>{HEADER_CSS}</style>
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 24, position: 'relative' }}>
        <Link
          to="/"
          onClick={() => {
            // The logo always returns home and starts at the top. When already
            // on '/', the pathname doesn't change so the global ScrollToTop
            // effect won't fire — reset scroll here to cover that case too.
            setMenuOpen(false)
            window.scrollTo(0, 0)
          }}
          style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, textDecoration: 'none', color: INK }}
        >
          <div
            className="font-mono-x"
            style={{ width: 38, height: 38, borderRadius: '50%', border: `2.5px solid ${TEAL}`, display: 'grid', placeItems: 'center', fontWeight: 800, color: TEAL, fontSize: 15 }}
          >
            C1
          </div>
          <div>
            <div className="font-display" style={{ fontSize: 19, fontWeight: 700, lineHeight: 1.1 }}>
              Open Navigator
            </div>
            <div className="v9-brand-sub" style={{ fontSize: 11.5, color: '#78716c' }}>
              by CommunityOne
            </div>
          </div>
        </Link>

        <button
          className="v9-burger"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen(!menuOpen)}
          style={{ width: 40, height: 40, border: '1px solid #e7e5e4', borderRadius: 10, background: '#fff', cursor: 'pointer', placeItems: 'center', fontSize: 18, color: INK }}
        >
          {menuOpen ? '✕' : '☰'}
        </button>

        <nav className={'v9-nav' + (menuOpen ? ' open' : '')} style={{ display: 'flex', gap: 22, marginLeft: 'auto', alignItems: 'center' }}>
          {navItems.map(({ label, onClick, active }) => (
            <button
              key={label}
              className={'v9-navlink' + (active ? ' active' : '')}
              onClick={() => {
                setMenuOpen(false)
                onClick()
              }}
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
                onClick={() => setShowLoginMenu(!showLoginMenu)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: '4px 6px' }}
              >
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name || user.email} referrerPolicy="no-referrer" style={{ width: 34, height: 34, borderRadius: '50%', border: `2px solid ${TEAL}`, objectFit: 'cover' }} />
                ) : (
                  <span style={{ width: 34, height: 34, borderRadius: '50%', background: TEAL, color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 14 }}>
                    {(user.full_name || user.username || user.email).charAt(0).toUpperCase()}
                  </span>
                )}
                <span style={{ fontSize: 14, fontWeight: 600, color: '#44403c' }}>
                  {user.full_name || user.username || user.email.split('@')[0]}
                </span>
              </button>
              {showLoginMenu && (
                <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 200, background: '#fff', border: '1px solid #e7e5e4', borderRadius: 12, boxShadow: '0 16px 32px rgba(28,25,23,0.12)', padding: 6, zIndex: 60 }}>
                  <button onClick={() => { setShowLoginMenu(false); navigate('/data-explorer/map/us/2024/median_household_income') }} style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, fontWeight: 600, color: TEAL_DARK, cursor: 'pointer', fontFamily: 'inherit', borderBottom: '1px solid #f5f5f4', marginBottom: 4, borderRadius: 8 }}>Explore Now</button>
                  <button onClick={() => { setShowLoginMenu(false); navigate('/profile') }} style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8 }}>My Profile</button>
                  <button onClick={() => { setShowLoginMenu(false); navigate('/settings') }} style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8 }}>Settings</button>
                  {user.is_admin && (
                    <button onClick={() => { setShowLoginMenu(false); navigate('/admin') }} style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8 }}>Admin</button>
                  )}
                  {user.is_admin && (
                    <>
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', color: '#a8a29e', padding: '8px 12px 2px', borderTop: '1px solid #f5f5f4', marginTop: 4 }}>Databricks</div>
                      <a href={DATABRICKS_WORKSPACE_URL} target="_blank" rel="noopener noreferrer" onClick={() => setShowLoginMenu(false)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px', fontSize: 14, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8, textDecoration: 'none' }}>Workspace ↗</a>
                      <a href={DATABRICKS_APP_URL} target="_blank" rel="noopener noreferrer" onClick={() => setShowLoginMenu(false)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px', fontSize: 14, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8, textDecoration: 'none' }}>App ↗</a>
                    </>
                  )}
                  <button onClick={() => { setShowLoginMenu(false); logout() }} style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, color: '#dc2626', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', borderTop: '1px solid #f5f5f4', marginTop: 4, borderRadius: 8 }}>Sign out</button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowLoginMenu(!showLoginMenu)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: INK, color: '#fff', border: 'none', borderRadius: 10, padding: '10px 18px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                <span>Register/Login</span>
                <span style={{ fontSize: 11 }}>▾</span>
              </button>
              {showLoginMenu && (
                <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 220, background: '#fff', border: '1px solid #e7e5e4', borderRadius: 12, boxShadow: '0 16px 32px rgba(28,25,23,0.12)', padding: 8, zIndex: 60 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#78716c', padding: '4px 8px 8px' }}>Sign in with:</div>
                  {(['google', 'facebook', 'github', 'huggingface'] as const).map((provider) => (
                    <button
                      key={provider}
                      onClick={() => { setShowLoginMenu(false); login(provider) }}
                      style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '10px 12px', fontSize: 14, fontWeight: 600, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit', borderRadius: 8, textTransform: 'capitalize' }}
                    >
                      {provider === 'huggingface' ? 'HuggingFace' : provider}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}
