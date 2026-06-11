import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, Fragment } from 'react'
import { Menu, Transition } from '@headlessui/react'
import {
  Cog6ToothIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  XMarkIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  ChevronDownIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'

// Pages that render their own prominent search box; on these we hide the
// redundant global search in the header.
const SEARCH_STYLE_PATHS = ['/search', '/documents']

export default function Layout() {
  const location = useLocation()
  // Search-style pages own a prominent search box of their own, so we hide the
  // redundant header search there. Add a route here to opt it into that.
  const isSearchStylePage = SEARCH_STYLE_PATHS.includes(location.pathname)
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  const { user, isAuthenticated, login, logout, isLoading, authError, clearAuthError } = useAuth()

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

          {/* Global Search - Hidden on home page, on search-style pages that
              have their own search box (see SEARCH_STYLE_PATHS), and mobile */}
          {location.pathname !== '/' && !isSearchStylePage && (
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

      {/* Main content — full width (global sidebar removed; home page is the nav hub) */}
      <div className="flex w-full min-w-0 min-h-[calc(100dvh-5rem)] flex-col bg-slate-300 pt-16">
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
