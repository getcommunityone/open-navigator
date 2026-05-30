import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tab } from '@headlessui/react'
import api from '../lib/api'
import { 
  UserIcon, 
  BuildingLibraryIcon,
  HeartIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'
import SocialStats from '../components/SocialStats'
import FollowButton from '../components/FollowButton'

interface Leader {
  id: number
  name: string
  slug: string
  title?: string
  photo_url?: string
  office?: string
  city?: string
  state?: string
  follower_count: number
  is_verified: boolean
}

interface Organization {
  id: number
  name: string
  slug: string
  description?: string
  logo_url?: string
  org_type?: string
  city?: string
  state?: string
  follower_count: number
  is_verified: boolean
}

interface Cause {
  id: number
  name: string
  slug: string
  description?: string
  icon_url?: string
  color?: string
  category?: string
  follower_count: number
}

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}

export default function Profile() {
  const { user } = useAuth()
  const [selectedTab, setSelectedTab] = useState(0)

  const { data: leadersFollowing } = useQuery<Leader[]>({
    queryKey: ['following', 'leaders'],
    queryFn: async () => {
      const response = await api.get('/social/following/leaders')
      return response.data
    },
    enabled: !!user
  })

  const { data: orgsFollowing } = useQuery<Organization[]>({
    queryKey: ['following', 'organizations'],
    queryFn: async () => {
      const response = await api.get('/social/following/organizations')
      return response.data
    },
    enabled: !!user
  })

  const { data: causesFollowing } = useQuery<Cause[]>({
    queryKey: ['following', 'causes'],
    queryFn: async () => {
      const response = await api.get('/social/following/causes')
      return response.data
    },
    enabled: !!user
  })

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
        {/* Profile Header */}
        <div className="bg-white rounded-lg shadow-md p-8 mb-6">
          <div className="flex items-start gap-6">
            {/* Avatar */}
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

            {/* Profile Info */}
            <div className="flex-1">
              <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
                {user.full_name || 'Community Member'}
              </h1>
              <p className="text-gray-600 mb-4">
                {user.email}
              </p>
              
              {user.city && user.state && (
                <p className="text-sm text-gray-500 mb-4">
                  📍 {user.city}, {user.state}
                </p>
              )}

              {/* Social Stats */}
              <SocialStats showBreakdown={true} clickable={false} />
            </div>

            {/* Edit Profile Button */}
            <a 
              href="/settings"
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Cog6ToothIcon className="h-5 w-5" />
              <span>Edit Profile</span>
            </a>
          </div>
        </div>

        {/* Following Tabs */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-2xl font-bold mb-6" style={{ color: '#354F52' }}>
            Following
          </h2>

          <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
            <Tab.List className="flex gap-2 border-b border-gray-200 mb-6">
              <Tab
                className={({ selected }) =>
                  classNames(
                    'px-4 py-2 font-medium text-sm border-b-2 transition-colors',
                    selected
                      ? 'border-[#354F52] text-[#354F52]'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  )
                }
              >
                <div className="flex items-center gap-2">
                  <UserIcon className="h-5 w-5" />
                  Leaders ({leadersFollowing?.length || 0})
                </div>
              </Tab>
              <Tab
                className={({ selected }) =>
                  classNames(
                    'px-4 py-2 font-medium text-sm border-b-2 transition-colors',
                    selected
                      ? 'border-[#354F52] text-[#354F52]'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  )
                }
              >
                <div className="flex items-center gap-2">
                  <BuildingLibraryIcon className="h-5 w-5" />
                  Charities ({orgsFollowing?.length || 0})
                </div>
              </Tab>
              <Tab
                className={({ selected }) =>
                  classNames(
                    'px-4 py-2 font-medium text-sm border-b-2 transition-colors',
                    selected
                      ? 'border-[#354F52] text-[#354F52]'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  )
                }
              >
                <div className="flex items-center gap-2">
                  <HeartIcon className="h-5 w-5" />
                  Causes ({causesFollowing?.length || 0})
                </div>
              </Tab>
            </Tab.List>

            <Tab.Panels>
              {/* Leaders */}
              <Tab.Panel>
                {!leadersFollowing || leadersFollowing.length === 0 ? (
                  <div className="text-center py-12">
                    <UserIcon className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">You're not following any leaders yet</p>
                    <a 
                      href="/people" 
                      className="inline-block mt-4 text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Find leaders to follow →
                    </a>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {leadersFollowing.map((leader) => (
                      <div 
                        key={leader.id} 
                        className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                      >
                        {leader.photo_url ? (
                          <img 
                            src={leader.photo_url} 
                            alt={leader.name}
                            className="h-16 w-16 rounded-full object-cover"
                          />
                        ) : (
                          <div 
                            className="h-16 w-16 rounded-full flex items-center justify-center text-white text-xl font-bold"
                            style={{ backgroundColor: '#354F52' }}
                          >
                            {leader.name.charAt(0)}
                          </div>
                        )}
                        <div className="flex-1">
                          <h3 className="font-semibold" style={{ color: '#354F52' }}>
                            {leader.name}
                            {leader.is_verified && <span className="ml-1 text-blue-500">✓</span>}
                          </h3>
                          {leader.title && <p className="text-sm text-gray-600">{leader.title}</p>}
                          {leader.office && <p className="text-sm text-gray-500">{leader.office}</p>}
                          {leader.city && leader.state && (
                            <p className="text-xs text-gray-400 mt-1">
                              {leader.city}, {leader.state}
                            </p>
                          )}
                          <p className="text-xs text-gray-500 mt-1">
                            {leader.follower_count.toLocaleString()} followers
                          </p>
                        </div>
                        <FollowButton 
                          type="leader" 
                          id={leader.id}
                          initialFollowing={true}
                          initialCount={leader.follower_count}
                          showCount={false}
                          compact={true}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </Tab.Panel>

              {/* Organizations */}
              <Tab.Panel>
                {!orgsFollowing || orgsFollowing.length === 0 ? (
                  <div className="text-center py-12">
                    <BuildingLibraryIcon className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">You're not following any charities yet</p>
                    <a 
                      href="/nonprofits" 
                      className="inline-block mt-4 text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Find charities to follow →
                    </a>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {orgsFollowing.map((org) => (
                      <div 
                        key={org.id} 
                        className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                      >
                        {org.logo_url ? (
                          <img 
                            src={org.logo_url} 
                            alt={org.name}
                            className="h-16 w-16 rounded object-contain"
                          />
                        ) : (
                          <div 
                            className="h-16 w-16 rounded flex items-center justify-center text-white text-xl font-bold"
                            style={{ backgroundColor: '#52796F' }}
                          >
                            {org.name.charAt(0)}
                          </div>
                        )}
                        <div className="flex-1">
                          <h3 className="font-semibold" style={{ color: '#354F52' }}>
                            {org.name}
                            {org.is_verified && <span className="ml-1 text-blue-500">✓</span>}
                          </h3>
                          {org.org_type && (
                            <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800 capitalize mb-1">
                              {org.org_type}
                            </span>
                          )}
                          {org.description && (
                            <p className="text-sm text-gray-600 line-clamp-2">{org.description}</p>
                          )}
                          {org.city && org.state && (
                            <p className="text-xs text-gray-400 mt-1">
                              {org.city}, {org.state}
                            </p>
                          )}
                          <p className="text-xs text-gray-500 mt-1">
                            {org.follower_count.toLocaleString()} followers
                          </p>
                        </div>
                        <FollowButton 
                          type="organization" 
                          id={org.id}
                          initialFollowing={true}
                          initialCount={org.follower_count}
                          showCount={false}
                          compact={true}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </Tab.Panel>

              {/* Causes */}
              <Tab.Panel>
                {!causesFollowing || causesFollowing.length === 0 ? (
                  <div className="text-center py-12">
                    <HeartIcon className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">You're not following any causes yet</p>
                    <a 
                      href="/" 
                      className="inline-block mt-4 text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Explore causes →
                    </a>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {causesFollowing.map((cause) => (
                      <div 
                        key={cause.id} 
                        className="p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                      >
                        <div className="flex items-center gap-3 mb-2">
                          {cause.icon_url ? (
                            <img src={cause.icon_url} alt={cause.name} className="h-8 w-8" />
                          ) : (
                            <div 
                              className="h-8 w-8 rounded-full"
                              style={{ backgroundColor: cause.color || '#354F52' }}
                            />
                          )}
                          <h3 className="font-semibold flex-1" style={{ color: '#354F52' }}>
                            {cause.name}
                          </h3>
                        </div>
                        {cause.description && (
                          <p className="text-sm text-gray-600 mb-3">{cause.description}</p>
                        )}
                        {cause.category && (
                          <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-800 capitalize mb-2">
                            {cause.category}
                          </span>
                        )}
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-gray-500">
                            {cause.follower_count.toLocaleString()} followers
                          </p>
                          <FollowButton 
                            type="cause" 
                            id={cause.id}
                            initialFollowing={true}
                            initialCount={cause.follower_count}
                            showCount={false}
                            compact={true}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Tab.Panel>
            </Tab.Panels>
          </Tab.Group>
        </div>
      </div>
    </div>
  )
}
