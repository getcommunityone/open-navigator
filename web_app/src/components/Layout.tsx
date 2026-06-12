import { Outlet } from 'react-router-dom'
import { XMarkIcon, XCircleIcon } from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'
import SiteHeader from './SiteHeader'

export default function Layout() {
  const { authError, clearAuthError } = useAuth()

  return (
    <div className="min-h-screen bg-slate-300">
      {/* Shared top navigation — identical to the home page header. */}
      <SiteHeader />

      {/* Main content — full width (global sidebar removed; home page is the nav hub) */}
      <div className="flex w-full min-w-0 min-h-[calc(100dvh-5rem)] flex-col bg-slate-300">
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
