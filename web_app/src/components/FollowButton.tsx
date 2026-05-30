import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { UserPlusIcon, UserMinusIcon } from '@heroicons/react/24/outline'
import { CheckIcon } from '@heroicons/react/24/solid'

interface FollowButtonProps {
  type: 'user' | 'leader' | 'organization' | 'cause'
  id: number
  initialFollowing?: boolean
  initialCount?: number
  showCount?: boolean
  compact?: boolean
  onFollowChange?: (following: boolean, count: number) => void
}

export default function FollowButton({
  type,
  id,
  initialFollowing = false,
  initialCount = 0,
  showCount = true,
  compact = false,
  onFollowChange
}: FollowButtonProps) {
  const [isFollowing, setIsFollowing] = useState(initialFollowing)
  const [followerCount, setFollowerCount] = useState(initialCount)
  const [isHovered, setIsHovered] = useState(false)
  const queryClient = useQueryClient()

  const followMutation = useMutation({
    mutationFn: async () => {
      const endpoint = `/social/follow/${type}/${id}`
      const response = await api.post(endpoint)
      return response.data
    },
    onSuccess: (data) => {
      setIsFollowing(true)
      setFollowerCount(data.follower_count)
      onFollowChange?.(true, data.follower_count)
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['social', 'stats'] })
      queryClient.invalidateQueries({ queryKey: ['following', type] })
    }
  })

  const unfollowMutation = useMutation({
    mutationFn: async () => {
      const endpoint = `/social/follow/${type}/${id}`
      const response = await api.delete(endpoint)
      return response.data
    },
    onSuccess: (data) => {
      setIsFollowing(false)
      setFollowerCount(data.follower_count)
      onFollowChange?.(false, data.follower_count)
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['social', 'stats'] })
      queryClient.invalidateQueries({ queryKey: ['following', type] })
    }
  })

  const handleClick = () => {
    if (isFollowing) {
      unfollowMutation.mutate()
    } else {
      followMutation.mutate()
    }
  }

  const isLoading = followMutation.isPending || unfollowMutation.isPending

  // LinkedIn/Facebook style button
  if (compact) {
    return (
      <button
        onClick={handleClick}
        disabled={isLoading}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`
          inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium
          transition-all duration-200 border
          ${isFollowing 
            ? isHovered
              ? 'bg-red-50 border-red-300 text-red-700 hover:bg-red-100'
              : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
            : 'bg-blue-600 border-blue-600 text-white hover:bg-blue-700'
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
      >
        {isLoading ? (
          <span className="h-4 w-4 border-2 border-t-transparent border-current rounded-full animate-spin" />
        ) : isFollowing ? (
          <>
            {isHovered ? (
              <UserMinusIcon className="h-4 w-4" />
            ) : (
              <CheckIcon className="h-4 w-4" />
            )}
            <span>{isHovered ? 'Unfollow' : 'Following'}</span>
          </>
        ) : (
          <>
            <UserPlusIcon className="h-4 w-4" />
            <span>Follow</span>
          </>
        )}
      </button>
    )
  }

  // Full button with count
  return (
    <div className="inline-flex items-center gap-3">
      <button
        onClick={handleClick}
        disabled={isLoading}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`
          inline-flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold
          transition-all duration-200 border-2
          ${isFollowing 
            ? isHovered
              ? 'bg-red-50 border-red-400 text-red-700 hover:bg-red-100'
              : 'bg-white border-gray-300 text-gray-700 hover:border-gray-400'
            : 'bg-blue-600 border-blue-600 text-white hover:bg-blue-700'
          }
          disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md
        `}
      >
        {isLoading ? (
          <span className="h-5 w-5 border-2 border-t-transparent border-current rounded-full animate-spin" />
        ) : isFollowing ? (
          <>
            {isHovered ? (
              <UserMinusIcon className="h-5 w-5" />
            ) : (
              <CheckIcon className="h-5 w-5" />
            )}
            <span>{isHovered ? 'Unfollow' : 'Following'}</span>
          </>
        ) : (
          <>
            <UserPlusIcon className="h-5 w-5" />
            <span>Follow</span>
          </>
        )}
      </button>
      
      {showCount && (
        <span className="text-sm text-gray-600">
          {followerCount.toLocaleString()} {followerCount === 1 ? 'follower' : 'followers'}
        </span>
      )}
    </div>
  )
}
