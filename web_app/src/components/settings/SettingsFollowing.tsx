/**
 * Following lists (Leaders / Charities / Tags) — used under Settings → Person (#674).
 * Moved from Profile so following is managed in Settings tabs.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tab } from '@headlessui/react'
import {
  UserIcon,
  BuildingLibraryIcon,
  HeartIcon,
} from '@heroicons/react/24/outline'
import api from '../../lib/api'
import { formatCityState } from '../../utils/formatters'
import FollowButton from '../FollowButton'

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
  master_org_id: string
  name: string
  description?: string
  logo_url?: string
  org_type?: string
  city?: string
  state?: string
  follower_count: number
  is_verified?: boolean
}

interface Tag {
  tag_id: string
  label?: string
  description?: string
  category?: string
  breadcrumb?: string
  follower_count: number
}

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}

export default function SettingsFollowing() {
  const [selectedTab, setSelectedTab] = useState(0)

  const { data: leadersFollowing } = useQuery<Leader[]>({
    queryKey: ['following', 'leaders'],
    queryFn: async () => (await api.get('/social/following/leaders')).data,
  })

  const { data: orgsFollowing } = useQuery<Organization[]>({
    queryKey: ['following', 'organizations'],
    queryFn: async () => (await api.get('/social/following/organizations')).data,
  })

  const { data: tagsFollowing } = useQuery<Tag[]>({
    queryKey: ['following', 'tags'],
    queryFn: async () => (await api.get('/social/following/tags')).data,
  })

  const tabCls = ({ selected }: { selected: boolean }) =>
    classNames(
      'px-3 py-2 font-medium text-sm border-b-2 transition-colors whitespace-nowrap',
      selected
        ? 'border-[#354F52] text-[#354F52]'
        : 'border-transparent text-gray-500 hover:text-gray-700',
    )

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-1">Following</h2>
      <p className="text-sm text-gray-500 mb-4">
        People, charities, and tags you follow
      </p>

      <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
        <Tab.List className="flex gap-1 border-b border-gray-200 mb-4 overflow-x-auto">
          <Tab className={tabCls}>
            <span className="inline-flex items-center gap-1.5">
              <UserIcon className="h-4 w-4" />
              Leaders ({leadersFollowing?.length ?? 0})
            </span>
          </Tab>
          <Tab className={tabCls}>
            <span className="inline-flex items-center gap-1.5">
              <BuildingLibraryIcon className="h-4 w-4" />
              Charities ({orgsFollowing?.length ?? 0})
            </span>
          </Tab>
          <Tab className={tabCls}>
            <span className="inline-flex items-center gap-1.5">
              <HeartIcon className="h-4 w-4" />
              Tags ({tagsFollowing?.length ?? 0})
            </span>
          </Tab>
        </Tab.List>

        <Tab.Panels>
          <Tab.Panel>
            {!leadersFollowing?.length ? (
              <Empty
                icon={<UserIcon className="h-12 w-12 mx-auto text-gray-300 mb-3" />}
                message="You're not following any leaders yet"
                href="/people"
                linkLabel="Find leaders to follow →"
              />
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {leadersFollowing.map((leader) => (
                  <div
                    key={leader.id}
                    className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg"
                  >
                    {leader.photo_url ? (
                      <img
                        src={leader.photo_url}
                        alt={leader.name}
                        className="h-12 w-12 rounded-full object-cover"
                      />
                    ) : (
                      <div
                        className="h-12 w-12 rounded-full flex items-center justify-center text-white font-bold"
                        style={{ backgroundColor: '#354F52' }}
                      >
                        {leader.name.charAt(0)}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm" style={{ color: '#354F52' }}>
                        {leader.name}
                        {leader.is_verified && <span className="ml-1 text-blue-500">✓</span>}
                      </h3>
                      {leader.title && <p className="text-xs text-gray-600">{leader.title}</p>}
                      {leader.city && leader.state && (
                        <p className="text-xs text-gray-400">
                          {formatCityState(leader.city, leader.state)}
                        </p>
                      )}
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

          <Tab.Panel>
            {!orgsFollowing?.length ? (
              <Empty
                icon={<BuildingLibraryIcon className="h-12 w-12 mx-auto text-gray-300 mb-3" />}
                message="You're not following any charities yet"
                href="/nonprofits"
                linkLabel="Find charities to follow →"
              />
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {orgsFollowing.map((org) => (
                  <div
                    key={org.master_org_id}
                    className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg"
                  >
                    {org.logo_url ? (
                      <img
                        src={org.logo_url}
                        alt={org.name}
                        className="h-12 w-12 rounded object-contain"
                      />
                    ) : (
                      <div
                        className="h-12 w-12 rounded flex items-center justify-center text-white font-bold"
                        style={{ backgroundColor: '#52796F' }}
                      >
                        {org.name.charAt(0)}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm" style={{ color: '#354F52' }}>
                        {org.name}
                      </h3>
                      {org.description && (
                        <p className="text-xs text-gray-600 line-clamp-2">{org.description}</p>
                      )}
                    </div>
                    <FollowButton
                      type="organization"
                      id={org.master_org_id}
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

          <Tab.Panel>
            {!tagsFollowing?.length ? (
              <Empty
                icon={<HeartIcon className="h-12 w-12 mx-auto text-gray-300 mb-3" />}
                message="You're not following any tags yet"
                href="/"
                linkLabel="Explore tags →"
              />
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {tagsFollowing.map((tag) => (
                  <div
                    key={tag.tag_id}
                    className="flex items-start justify-between gap-3 p-3 border border-gray-200 rounded-lg"
                  >
                    <div className="min-w-0">
                      <h3 className="font-semibold text-sm" style={{ color: '#354F52' }}>
                        {tag.label || tag.tag_id}
                      </h3>
                      {tag.breadcrumb && (
                        <p className="text-xs text-gray-400">{tag.breadcrumb}</p>
                      )}
                    </div>
                    <FollowButton
                      type="tag"
                      id={tag.tag_id}
                      initialFollowing={true}
                      initialCount={tag.follower_count}
                      showCount={false}
                      compact={true}
                    />
                  </div>
                ))}
              </div>
            )}
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>
    </div>
  )
}

function Empty({
  icon,
  message,
  href,
  linkLabel,
}: {
  icon: React.ReactNode
  message: string
  href: string
  linkLabel: string
}) {
  return (
    <div className="text-center py-8">
      {icon}
      <p className="text-sm text-gray-500">{message}</p>
      <a href={href} className="inline-block mt-3 text-sm font-medium text-teal-800 hover:underline">
        {linkLabel}
      </a>
    </div>
  )
}
