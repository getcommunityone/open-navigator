import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, Fragment } from 'react'
import { Menu, Transition } from '@headlessui/react'
import {
  HomeIcon,
  MapIcon,
  DocumentTextIcon,
  BellAlertIcon,
  BuildingLibraryIcon,
  Cog6ToothIcon,
  ChartBarIcon,
  MagnifyingGlassIcon,
  BoltIcon,
  BookOpenIcon,
  UserGroupIcon,
  AcademicCapIcon,
  Bars3Icon,
  XMarkIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  ChevronDownIcon,
  MapPinIcon,
  HeartIcon,
  CodeBracketIcon,
  XCircleIcon,
  TagIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import ExploreQuickNavSidebarPanel from './ExploreQuickNavSidebarPanel'

const navigation = [
  { name: 'Home', href: '/', icon: HomeIcon },
  { name: 'Take Action', href: '/explore', icon: BoltIcon },
  { name: 'Search', href: '/search', icon: MagnifyingGlassIcon },
  { name: 'Jurisdictions', href: '/jurisdictions', icon: MapPinIcon },
  { 
    section: 'Citizens & Residents',
    items: [
      { name: 'Community Events', href: '/events', icon: BookOpenIcon },
      { name: 'Services & Resources', href: '/services', icon: HeartIcon },
    ]
  },
  { 
    section: 'Policy & Government',
    items: [
      { name: 'Policy Decisions', href: '/documents', icon: DocumentTextIcon },
      { name: 'Browse Topics', href: '/browse-topics', icon: TagIcon },
      { name: 'Money & Talk', href: '/money-and-talk', icon: BanknotesIcon },
      { name: 'Budget Analysis', href: '/analytics', icon: ChartBarIcon },
      { name: 'Elected Officials', href: '/people', icon: UserGroupIcon },
      { name: 'Public Policies', href: '/public-policies', icon: DocumentTextIcon },
      { name: 'Policy Map', href: '/policy-map', icon: MapIcon },
      { name: 'Data explorer', href: '/data-explorer', icon: MapIcon },
    ]
  },
  { 
    section: 'Community & Advocacy',
    items: [
      { name: 'Charities', href: '/nonprofits', icon: BuildingLibraryIcon },
      { name: 'Advocacy Topics', href: '/advocacy-topics', icon: BellAlertIcon },
      { name: 'Fact-Checking', href: '/fact-checking', icon: AcademicCapIcon },
    ]
  },
  { 
    section: 'Developers',
    items: [
      { name: 'Open Source', href: '/opensource', icon: CodeBracketIcon },
      { name: 'Hackathons', href: '/hackathons', icon: AcademicCapIcon },
    ]
  },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
]

function pathMatchesNavHref(pathname: string, href: string): boolean {
  if (href === '/data-explorer') {
    return pathname === '/data-explorer' || pathname.startsWith('/data-explorer/')
  }
  return pathname === href
}

export default function Layout() {
  const location = useLocation()
  const isExplorePage = location.pathname === '/explore'
  const isDataExplorerSection =
    location.pathname === '/data-explorer' || location.pathname.startsWith('/data-explorer/')
  const useExploreQuickNavSidebar = isExplorePage || isDataExplorerSection
  // Data explorer needs the full width for its map/scorecard layout, so the
  // app-wide sidebar is collapsed on desktop here (still reachable on mobile).
  const hideSidebarOnDesktop = isDataExplorerSection
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  const { user, isAuthenticated, login, logout, isLoading, authError, clearAuthError } = useAuth()
  const { location: userLocation, hasLocation } = useLocationContext()

  // Environment-aware URLs
  const docsUrl = import.meta.env.PROD ? 'https://www.communityone.com/docs/intro' : 'http://localhost:3000/docs/intro'
  const apiDocsUrl = import.meta.env.PROD ? 'https://www.communityone.com/api/docs' : 'http://localhost:8000/docs'

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`)
    }
  }

  const goToSearchPage = () => {
    navigate('/search')
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    })
  }

  return (
    <div className="min-h-screen bg-slate-300">
      {/* Top Header Bar */}
      <div className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="flex items-center justify-between px-4 md:px-6 py-3">
          <div className="flex items-center gap-3">
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-gray-100 text-gray-700"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <XMarkIcon className="h-6 w-6" />
              ) : (
                <Bars3Icon className="h-6 w-6" />
              )}
            </button>

            <Link to="/" className="flex items-center gap-2 md:gap-3 group">
              <img 
                src="/communityone_logo.svg" 
                alt="CommunityOne Logo" 
                className="h-10 md:h-12"
              />
              <div className="flex flex-col">
                <h1 className="text-lg md:text-2xl font-bold" style={{ color: '#354F52' }}>
                  Open Navigator
                </h1>
                <span className="hidden md:block text-xs text-gray-500 -mt-1 group-hover:text-[#354F52] transition-colors">
                  The open path to everything local
                </span>
              </div>
            </Link>
          </div>

          {/* Global Search - Hidden on home page and mobile */}
          {location.pathname !== '/' && (
            <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-2xl mx-8">
              <div className="relative w-full">
                <input
                  type="text"
                  placeholder="Search people, meetings, organizations, causes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              </div>
            </form>
          )}

          {/* Header Actions */}
          <div className="flex items-center gap-2 md:gap-4">
            {/* Location Banner - Compact */}
            {hasLocation && userLocation && (
              <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-primary-50 border border-primary-200 rounded-lg">
                <MapPinIcon className="h-4 w-4 text-primary-600 flex-shrink-0" />
                <div className="text-xs">
                  <div className="font-semibold text-gray-900">
                    {userLocation.city}, {userLocation.state}
                  </div>
                  {userLocation.county && (
                    <div className="text-gray-700">{userLocation.county}</div>
                  )}
                </div>
                <button
                  onClick={() => navigate('/?tab=community')}
                  className="text-xs text-primary-600 hover:text-primary-700 font-medium underline ml-2 flex-shrink-0"
                >
                  Change
                </button>
              </div>
            )}
            {/* Authentication */}
            {isLoading ? (
              <div className="px-3 py-2">
                <div className="animate-spin h-8 w-8 border-3 border-gray-300 border-t-primary-600 rounded-full"></div>
              </div>
            ) : isAuthenticated && user ? (
              <Menu as="div" className="relative">
                <Menu.Button className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
                  {user.avatar_url ? (
                    <img 
                      src={user.avatar_url} 
                      alt={user.full_name || user.email}
                      className="h-9 w-9 flex-shrink-0 rounded-full border-2 border-primary-500 shadow-sm object-cover"
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        console.error('❌ Avatar failed to load:', user.avatar_url);
                        // If image fails to load, hide it and show fallback
                        e.currentTarget.style.display = 'none';
                        const fallback = e.currentTarget.nextElementSibling as HTMLElement | null;
                        if (fallback) fallback.style.display = 'flex';
                      }}
                      onLoad={() => {
                        console.log('✅ Avatar loaded successfully:', user.avatar_url?.substring(0, 50));
                      }}
                    />
                  ) : null}
                  <div 
                    className="h-9 w-9 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center text-white font-bold text-sm shadow-sm"
                    style={{ display: user.avatar_url ? 'none' : 'flex' }}
                  >
                    {(user.full_name || user.username || user.email).charAt(0).toUpperCase()}
                  </div>
                  <span className="hidden md:inline text-sm font-medium text-gray-700">
                    {user.full_name || user.username || user.email.split('@')[0]}
                  </span>
                  <ChevronDownIcon className="hidden md:block h-4 w-4 text-gray-600" />
                </Menu.Button>
                
                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 focus:outline-none z-50">
                    <div className="px-4 py-3 border-b border-gray-200">
                      <div className="flex items-center gap-3 mb-2">
                        {user.avatar_url ? (
                          <img 
                            src={user.avatar_url} 
                            alt={user.full_name || user.email}
                            className="h-12 w-12 rounded-full border-2 border-primary-500"
                            referrerPolicy="no-referrer"
                            onError={(e) => {
                              console.error('❌ Avatar (dropdown) failed to load:', user.avatar_url);
                              // If image fails to load, hide it and show fallback
                              e.currentTarget.style.display = 'none';
                              const fallback = e.currentTarget.nextElementSibling as HTMLElement | null;
                              if (fallback) fallback.style.display = 'flex';
                            }}
                          />
                        ) : null}
                        <div 
                          className="h-12 w-12 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center text-white font-bold text-lg"
                          style={{ display: user.avatar_url ? 'none' : 'flex' }}
                        >
                          {(user.full_name || user.username || user.email).charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {user.full_name || user.username || user.email.split('@')[0]}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            {user.email}
                          </p>
                        </div>
                      </div>
                      {user.oauth_provider && (
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                          <span>Signed in via</span>
                          <span className="font-medium capitalize">{user.oauth_provider}</span>
                        </div>
                      )}
                    </div>
                    <div className="py-1">
                      <Menu.Item>
                        {({ active }) => (
                          <button
                            onClick={() => navigate('/profile')}
                            className={`${
                              active ? 'bg-gray-50' : ''
                            } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:text-gray-900`}
                          >
                            <UserCircleIcon className="h-5 w-5" />
                            <span>My Profile</span>
                          </button>
                        )}
                      </Menu.Item>
                      <Menu.Item>
                        {({ active }) => (
                          <button
                            onClick={() => navigate('/settings')}
                            className={`${
                              active ? 'bg-gray-50' : ''
                            } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:text-gray-900`}
                          >
                            <Cog6ToothIcon className="h-5 w-5" />
                            <span>Settings</span>
                          </button>
                        )}
                      </Menu.Item>
                      <Menu.Item>
                        {({ active }) => (
                          <button
                            onClick={logout}
                            className={`${
                              active ? 'bg-red-50' : ''
                            } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:text-red-700 border-t border-gray-100 mt-1`}
                          >
                            <ArrowRightOnRectangleIcon className="h-5 w-5" />
                            <span className="font-medium">Sign out</span>
                          </button>
                        )}
                      </Menu.Item>
                    </div>
                  </Menu.Items>
                </Transition>
              </Menu>
            ) : (
              <div className="relative">
                <button
                  onClick={() => setShowLoginMenu(!showLoginMenu)}
                  className="px-3 md:px-4 py-2 text-white rounded-lg transition-colors text-sm md:text-base font-medium flex items-center gap-2"
                  style={{ backgroundColor: '#354F52' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
                >
                  <UserCircleIcon className="h-5 w-5" />
                  <span className="hidden md:inline">Register/Login</span>
                  <ChevronDownIcon className="h-4 w-4" />
                </button>
                
                {showLoginMenu && (
                  <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                    <div className="px-4 py-2 border-b border-gray-200">
                      <p className="text-sm font-medium text-gray-900">Sign in with:</p>
                    </div>
                    <button
                      onClick={() => { login('google'); setShowLoginMenu(false); }}
                      className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                        <svg viewBox="0 0 24 24" className="w-5 h-5" preserveAspectRatio="xMidYMid meet">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                      </div>
                      <span className="text-sm font-medium text-gray-700">Google</span>
                    </button>
                    <button
                      onClick={() => { login('facebook'); setShowLoginMenu(false); }}
                      className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-6 h-6 flex items-center justify-center">
                        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#1877F2">
                          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                        </svg>
                      </div>
                      <span className="text-sm font-medium text-gray-700">Facebook</span>
                    </button>
                    <button
                      onClick={() => { login('github'); setShowLoginMenu(false); }}
                      className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-6 h-6 flex items-center justify-center">
                        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#181717">
                          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                        </svg>
                      </div>
                      <span className="text-sm font-medium text-gray-700">GitHub</span>
                    </button>
                    <div className="border-t border-gray-100 my-1"></div>
                    <button
                      onClick={() => { login('huggingface'); setShowLoginMenu(false); }}
                      className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-6 h-6 flex items-center justify-center">
                        <span className="text-2xl">🤗</span>
                      </div>
                      <span className="text-sm font-medium text-gray-700">HuggingFace</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              onClick={goToSearchPage}
              className="flex items-center gap-1.5 px-2 md:px-3 py-2 text-gray-700 hover:text-primary-600 transition-colors font-medium"
            >
              <MagnifyingGlassIcon className="h-5 w-5 shrink-0" aria-hidden />
              <span>Search</span>
            </button>
            
            <a
              href={docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 md:gap-2 px-2 md:px-4 py-2 text-gray-700 hover:text-primary-600 transition-colors"
            >
              <BookOpenIcon className="h-5 w-5" />
              <span className="hidden md:inline font-medium">Docs</span>
            </a>
            <a
              href={apiDocsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2 md:px-4 py-2 text-white rounded-lg transition-colors text-sm md:text-base"
              style={{ backgroundColor: '#354F52' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
            >
              API
            </a>
          </div>
        </div>
      </div>

      {/* Sidebar — on /explore and Data explorer, match home Quick Navigation (expand/collapse shortcut panels) */}
      <div
        className={`
        fixed top-16 inset-y-0 left-0 border-r border-gray-200 z-40
        transform transition-transform duration-200 ease-in-out
        ${useExploreQuickNavSidebar ? 'w-72 bg-slate-300' : 'w-64 bg-white'}
        ${mobileMenuOpen ? 'translate-x-0' : hideSidebarOnDesktop ? '-translate-x-full' : '-translate-x-full md:translate-x-0'}
      `}
      >
        {useExploreQuickNavSidebar ? (
          <ExploreQuickNavSidebarPanel
            onNavigate={() => setMobileMenuOpen(false)}
            deferSectionNavigationMs={isDataExplorerSection ? 280 : undefined}
          />
        ) : (
          <>
            <nav className="mt-6 px-4 overflow-y-auto h-[calc(100vh-10rem)]">
              {navigation.map((item, index) => {
                // Handle section headers with nested items
                if ('section' in item && item.section && item.items) {
                  return (
                    <div key={index} className="mb-6">
                      <div className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {item.section}
                      </div>
                      {item.items.map((subItem) => {
                        const isActive = pathMatchesNavHref(location.pathname, subItem.href)
                        const isExternal = 'external' in subItem && subItem.external

                        const linkClasses = `
                      flex items-center gap-3 px-4 py-3 mb-1 rounded-lg transition-colors
                      ${
                        isActive
                          ? 'bg-primary-50 text-primary-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-100'
                      }
                    `

                        if (isExternal) {
                          return (
                            <a
                              key={subItem.name}
                              href={subItem.href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={linkClasses}
                            >
                              <subItem.icon className="h-5 w-5" />
                              <span className="text-sm">{subItem.name}</span>
                            </a>
                          )
                        }

                        return (
                          <Link
                            key={subItem.name}
                            to={subItem.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={linkClasses}
                          >
                            <subItem.icon className="h-5 w-5" />
                            <span className="text-sm">{subItem.name}</span>
                          </Link>
                        )
                      })}
                    </div>
                  )
                }

                // Handle regular navigation items
                if ('href' in item && item.href) {
                  const isActive = pathMatchesNavHref(location.pathname, item.href)
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      onClick={() => {
                        setMobileMenuOpen(false)
                        if (item.href === '/search') {
                          window.requestAnimationFrame(() => {
                            window.scrollTo({ top: 0, behavior: 'smooth' })
                          })
                        }
                      }}
                      className={`
                    flex items-center gap-3 px-4 py-3 mb-2 rounded-lg transition-colors
                    ${
                      isActive
                        ? 'bg-primary-50 text-primary-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-100'
                    }
                  `}
                    >
                      <item.icon className="h-6 w-6" />
                      <span>{item.name}</span>
                    </Link>
                  )
                }

                return null
              })}
            </nav>

            {/* Sidebar Footer */}
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 bg-white">
              <div className="text-sm text-gray-600">
                <div className="font-medium mb-1">Open Data Sources</div>
                <div className="text-xs">
                  • <Link to="/jurisdictions" className="hover:text-primary-600 hover:underline">925 Jurisdictions</Link>
                  <br />
                  • <Link to="/search?types=organizations" className="hover:text-primary-600 hover:underline">
                    43,726 Nonprofits
                  </Link>
                  <br />
                  • 6,913 Meeting Pages
                  <br />
                  • <Link to="/search?types=contacts" className="hover:text-primary-600 hover:underline">
                    362 Officials
                  </Link>
                </div>
                <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                  <Link
                    to="/#contact"
                    className="block text-xs text-primary-600 hover:text-primary-700 hover:underline font-medium"
                  >
                    📍 Request Jurisdiction Coverage
                  </Link>
                  <Link
                    to="/support"
                    className="block text-xs text-primary-600 hover:text-primary-700 hover:underline font-medium"
                  >
                    💬 Contact support
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Main content */}
      <div
        className={`flex w-full min-w-0 min-h-[calc(100dvh-5rem)] flex-col bg-slate-300 pt-16 ${hideSidebarOnDesktop ? 'md:pl-0' : useExploreQuickNavSidebar ? 'md:pl-72' : 'md:pl-64'}`}
      >
        {/* Auth Error Banner - Mobile Friendly */}
        {authError && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 m-4">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <XCircleIcon className="h-5 w-5 text-red-500" aria-hidden="true" />
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm font-medium text-red-800">
                  Login failed
                </p>
                <p className="mt-1 text-sm text-red-700">
                  {authError}
                </p>
              </div>
              <div className="ml-auto pl-3">
                <button
                  onClick={clearAuthError}
                  className="inline-flex rounded-md bg-red-50 p-1.5 text-red-500 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-600 focus:ring-offset-2 focus:ring-offset-red-50"
                >
                  <span className="sr-only">Dismiss</span>
                  <XMarkIcon className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        )}
        <main className="flex min-h-0 flex-1 flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
