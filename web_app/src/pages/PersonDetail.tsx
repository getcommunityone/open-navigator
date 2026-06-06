import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import api from '../lib/api'
import {
  ArrowLeftIcon,
  MapPinIcon,
  EnvelopeIcon,
  PhoneIcon,
  BuildingOffice2Icon,
  GlobeAltIcon,
  DocumentTextIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'

interface PersonOrganization {
  title: string | null
  organization: string | null
  master_org_id: string | null
  compensation: number | null
}

interface PersonColleague {
  person_uid: string
  name: string
  title: string | null
  photo_url: string | null
}

interface Person {
  master_person_id: string
  name: string
  state_code: string | null
  city: string | null
  email: string | null
  phone: string | null
  jurisdiction_website: string | null
  photo_url: string | null
  biography: string | null
  organizations: PersonOrganization[]
  colleagues: PersonColleague[]
}

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export default function PersonDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const routerLocation = useLocation()
  const [person, setPerson] = useState<Person | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    if (!id) {
      setError('No person id provided')
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    api
      .get<Person>(`/person/${id}`)
      .then((response) => {
        if (!cancelled) {
          setPerson(response.data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            (err as any)?.response?.data?.detail ||
              (err as any)?.message ||
              'Unable to load person details',
          )
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [id])

  // Return the user to the screen they came from (e.g. their leaders/people
  // search, whose query + filters live in the URL). `location.key` is
  // 'default' only when this page is the first in-app entry (opened via a
  // direct link or refresh), in which case we fall back to the People list.
  const handleBack = () => {
    if (routerLocation.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/people')
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex justify-center items-center h-96">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading person details...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !person) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Person not found</h3>
            <p className="text-red-700 mb-4">
              {error || 'We could not find a person with that id.'}
            </p>
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              Back to People
            </button>
          </div>
        </div>
      </div>
    )
  }

  const location = [person.city, person.state_code].filter(Boolean).join(', ')

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <div className="mb-6">
          <button
            type="button"
            onClick={handleBack}
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to People
          </button>
        </div>

        {/* Person Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-start gap-5">
            {/* Headshot (local leaders) with a letter-avatar fallback */}
            {person.photo_url ? (
              <img
                src={person.photo_url}
                alt={person.name}
                className="h-24 w-24 rounded-full object-cover bg-gray-100 flex-shrink-0"
                onError={(e) => {
                  ;(e.currentTarget as HTMLImageElement).style.display = 'none'
                  const fallback = e.currentTarget
                    .nextElementSibling as HTMLElement | null
                  if (fallback) fallback.style.display = 'flex'
                }}
              />
            ) : null}
            <div
              className="h-24 w-24 rounded-full bg-blue-100 text-blue-700 text-3xl font-semibold items-center justify-center flex-shrink-0"
              style={{ display: person.photo_url ? 'none' : 'flex' }}
            >
              {person.name.charAt(0)}
            </div>

            <div className="flex-1 min-w-0">
              <h1 className="text-3xl font-bold text-gray-900 mb-3">{person.name}</h1>

              {location && (
                <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                  <MapPinIcon className="h-4 w-4" />
                  <span>{location}</span>
                </div>
              )}

              {person.jurisdiction_website && (
                <a
                  href={person.jurisdiction_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 hover:underline mb-4"
                >
                  <GlobeAltIcon className="h-4 w-4" />
                  {person.jurisdiction_website.replace(/^https?:\/\//, '')}
                </a>
              )}

              {(person.email || person.phone) && (
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  {person.email && (
                <a
                  href={`mailto:${person.email}`}
                  className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:underline"
                >
                  <EnvelopeIcon className="h-4 w-4" />
                  {person.email}
                </a>
              )}
              {person.phone && (
                <a
                  href={`tel:${person.phone}`}
                  className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 hover:underline"
                >
                  <PhoneIcon className="h-4 w-4" />
                  {person.phone}
                </a>
              )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Biography (local leaders with a curated bio, e.g. a mayor) */}
        {person.biography && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <DocumentTextIcon className="h-5 w-5" />
              Biography
            </h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {person.biography}
            </p>
          </div>
        )}

        {/* Organizations */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <BuildingOffice2Icon className="h-5 w-5" />
            Organizations
          </h2>

          {person.organizations.length === 0 ? (
            <p className="text-sm text-gray-500">
              No organization affiliations on record.
            </p>
          ) : (
            <div className="space-y-3">
              {person.organizations.map((org, idx) => (
                <div
                  key={org.master_org_id ?? idx}
                  className="border border-gray-100 rounded-lg p-4 hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-gray-900">
                        {org.title || 'Member'}
                      </div>
                      {org.organization && (
                        <div className="text-sm text-gray-600">
                          @ {org.organization}
                        </div>
                      )}
                    </div>
                    {org.compensation != null && (
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 whitespace-nowrap">
                        {usd.format(org.compensation)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Other officials in the same jurisdiction (officials only) — cross-nav
            to each peer's own detail page. */}
        {person.colleagues.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 mt-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <UserGroupIcon className="h-5 w-5" />
              Other officials{person.city ? ` in ${person.city}` : ''}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {person.colleagues.map((c) => (
                <Link
                  key={c.person_uid}
                  to={`/person/${encodeURIComponent(c.person_uid)}`}
                  className="flex items-center gap-3 border border-gray-100 rounded-lg p-3 hover:shadow-sm hover:border-blue-200 transition-all"
                >
                  {c.photo_url ? (
                    <img
                      src={c.photo_url}
                      alt={c.name}
                      className="h-10 w-10 rounded-full object-cover bg-gray-100 flex-shrink-0"
                      onError={(e) => {
                        ;(e.currentTarget as HTMLImageElement).style.display = 'none'
                        const fallback = e.currentTarget
                          .nextElementSibling as HTMLElement | null
                        if (fallback) fallback.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div
                    className="h-10 w-10 rounded-full bg-blue-100 text-blue-700 text-sm font-semibold items-center justify-center flex-shrink-0"
                    style={{ display: c.photo_url ? 'none' : 'flex' }}
                  >
                    {c.name.charAt(0)}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-gray-900 truncate">
                      {c.name}
                    </div>
                    {c.title && (
                      <div className="text-xs text-gray-500 truncate">{c.title}</div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
