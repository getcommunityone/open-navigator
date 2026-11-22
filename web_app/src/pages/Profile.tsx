/**
 * Public profile summary. Following is managed under Settings → Person (#674).
 */
import { Link } from 'react-router-dom'
import { Cog6ToothIcon } from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'
import SocialStats from '../components/SocialStats'

export default function Profile() {
  const { user } = useAuth()

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#F1F5F9' }}>
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4" style={{ color: '#354F52' }}>
            Please sign in
          </h2>
          <p className="text-gray-600">You need to be signed in to view your profile</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-md p-8 mb-6">
          <div className="flex items-start gap-6">
            <div className="flex-shrink-0">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.full_name || user.email}
                  className="h-24 w-24 rounded-full object-cover border-4 border-gray-200"
                />
              ) : (
                <div
                  className="h-24 w-24 rounded-full flex items-center justify-center text-white text-3xl font-bold"
                  style={{ backgroundColor: '#354F52' }}
                >
                  {(user.full_name || user.email).charAt(0).toUpperCase()}
                </div>
              )}
            </div>

            <div className="flex-1">
              <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
                {user.full_name || 'Community Member'}
              </h1>
              <p className="text-gray-600 mb-4">{user.email}</p>
              {user.city && user.state && (
                <p className="text-sm text-gray-500 mb-4">
                  📍 {user.city}, {user.state}
                </p>
              )}
              <SocialStats showBreakdown={true} clickable={false} />
            </div>

            <Link
              to="/settings?section=account&tab=profile"
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Cog6ToothIcon className="h-5 w-5" />
              <span>Settings</span>
            </Link>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold mb-2" style={{ color: '#354F52' }}>
            Following
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Manage leaders, charities, and tags you follow in Settings.
          </p>
          <Link
            to="/settings?section=account&tab=following"
            className="inline-flex text-sm font-medium text-teal-800 hover:underline"
          >
            Open Following in Settings →
          </Link>
        </div>
      </div>
    </div>
  )
}
