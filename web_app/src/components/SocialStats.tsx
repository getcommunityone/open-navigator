import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { UserGroupIcon, UserPlusIcon } from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

interface SocialStatsProps {
  userId?: number
  showBreakdown?: boolean
  clickable?: boolean
}

interface FollowerStats {
  followers: number
  following: number
  following_users: number
  following_leaders: number
  following_organizations: number
  following_causes: number
}

export default function SocialStats({ 
  userId, 
  showBreakdown = false,
  clickable = true 
}: SocialStatsProps) {
  const { data: stats, isLoading } = useQuery<FollowerStats>({
    queryKey: ['social', 'stats', userId],
    queryFn: async () => {
      const params = userId ? `?user_id=${userId}` : ''
      const response = await api.get(`/social/stats${params}`)
      return response.data
    }
  })

  if (isLoading) {
    return (
      <div className="animate-pulse flex gap-6">
        <div className="h-5 w-20 bg-gray-200 rounded"></div>
        <div className="h-5 w-20 bg-gray-200 rounded"></div>
      </div>
    )
  }

  if (!stats) return null

  const StatsContent = () => (
    <>
      {/* LinkedIn-style stat display */}
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <UserGroupIcon className="h-5 w-5" style={{ color: '#52796F' }} />
          <span className="font-semibold" style={{ color: '#354F52' }}>
            {stats.followers.toLocaleString()}
          </span>
          <span className="text-gray-600">
            {stats.followers === 1 ? 'Follower' : 'Followers'}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <UserPlusIcon className="h-5 w-5" style={{ color: '#52796F' }} />
          <span className="font-semibold" style={{ color: '#354F52' }}>
            {stats.following.toLocaleString()}
          </span>
          <span className="text-gray-600">Following</span>
        </div>
      </div>

      {/* Breakdown of what they're following */}
      {showBreakdown && stats.following > 0 && (
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {stats.following_leaders > 0 && (
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="font-semibold text-blue-900">
                {stats.following_leaders}
              </div>
              <div className="text-blue-700 text-xs">Leaders</div>
            </div>
          )}
          
          {stats.following_organizations > 0 && (
            <div className="bg-green-50 rounded-lg p-3">
              <div className="font-semibold text-green-900">
                {stats.following_organizations}
              </div>
              <div className="text-green-700 text-xs">Charities</div>
            </div>
          )}
          
          {stats.following_causes > 0 && (
            <div className="bg-purple-50 rounded-lg p-3">
              <div className="font-semibold text-purple-900">
                {stats.following_causes}
              </div>
              <div className="text-purple-700 text-xs">Causes</div>
            </div>
          )}
          
          {stats.following_users > 0 && (
            <div className="bg-orange-50 rounded-lg p-3">
              <div className="font-semibold text-orange-900">
                {stats.following_users}
              </div>
              <div className="text-orange-700 text-xs">People</div>
            </div>
          )}
        </div>
      )}
    </>
  )

  if (clickable) {
    return (
      <Link to="/profile/following" className="hover:opacity-75 transition-opacity">
        <StatsContent />
      </Link>
    )
  }

  return <StatsContent />
}
