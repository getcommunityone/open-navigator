import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import api from '../lib/api'
import { formatCurrency, formatCityState } from '../utils/formatters'
import {
  ArrowLeftIcon,
  MapPinIcon,
  BuildingOffice2Icon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'

interface Grant {
  grant_id: string
  grantor_name: string | null
  grantor_master_org_id: string | null
  grantor_ein: string | null
  grantor_state_code: string | null
  grantor_city: string | null
  grantee_name: string | null
  grantee_master_org_id: string | null
  grantee_ein: string | null
  grantee_city: string | null
  grantee_state_code: string | null
  grantee_zip: string | null
  amount: number | null
  noncash_assistance_amount: number | null
  valuation_method: string | null
  noncash_description: string | null
  irc_section: string | null
  purpose: string | null
  tax_year: string | null
  source_url: string | null
}

export default function GrantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [grant, setGrant] = useState<Grant | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Return to wherever the user came from (e.g. the homepage money-flow chart);
  // fall back to /search only on a direct/cold load with no in-app history.
  const goBack = () => {
    if (location.key && location.key !== 'default') navigate(-1)
    else navigate('/search')
  }

  useEffect(() => {
    let cancelled = false

    if (!id) {
      setError('No grant id provided')
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    api
      .get<Grant>(`/grants/${id}`)
      .then((response) => {
        if (!cancelled) {
          setGrant(response.data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            (err as any)?.response?.data?.detail ||
              (err as any)?.message ||
              'Unable to load grant details',
          )
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [id])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex justify-center items-center h-96">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading grant details...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !grant) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Grant not found</h3>
            <p className="text-red-700 mb-4">
              {error || 'We could not find a grant with that id.'}
            </p>
            <button
              type="button"
              onClick={goBack}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              Back
            </button>
          </div>
        </div>
      </div>
    )
  }

  const grantorName = grant.grantor_name || 'Unknown grantor'
  const granteeName = grant.grantee_name || 'Unknown grantee'

  const grantorLocation = formatCityState(grant.grantor_city, grant.grantor_state_code)
  const granteeLocation = [
    formatCityState(grant.grantee_city, grant.grantee_state_code),
    grant.grantee_zip,
  ]
    .filter(Boolean)
    .join(', ')

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <div className="mb-6">
          <button
            type="button"
            onClick={goBack}
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back
          </button>
        </div>

        {/* Grant Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <h1 className="text-3xl font-bold text-gray-900">
              {grantorName} <span className="text-gray-400">→</span> {granteeName}
            </h1>
            {grant.amount != null && (
              <span className="inline-flex items-center px-4 py-2 rounded-full text-lg font-semibold bg-green-100 text-green-800 whitespace-nowrap">
                {formatCurrency(grant.amount)}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            {grant.tax_year && (
              <span className="inline-flex items-center px-3 py-1 rounded-full font-medium bg-blue-100 text-blue-800">
                Tax year {grant.tax_year}
              </span>
            )}
            {grant.irc_section && (
              <span className="inline-flex items-center px-3 py-1 rounded-full font-medium bg-purple-100 text-purple-800">
                IRC {grant.irc_section}
              </span>
            )}
          </div>

          {grant.purpose && (
            <p className="mt-4 text-gray-700 leading-relaxed">{grant.purpose}</p>
          )}
        </div>

        {/* Grantor / Grantee */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Grantor */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <BuildingOffice2Icon className="h-5 w-5" />
              Grantor
            </h2>
            <div className="text-lg font-semibold text-gray-900">{grantorName}</div>
            {grant.grantor_ein && (
              <div className="text-sm text-gray-600 mt-1">EIN: {grant.grantor_ein}</div>
            )}
            {grantorLocation && (
              <div className="flex items-center gap-2 text-sm text-gray-600 mt-2">
                <MapPinIcon className="h-4 w-4" />
                <span>{grantorLocation}</span>
              </div>
            )}
          </div>

          {/* Grantee */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <BuildingOffice2Icon className="h-5 w-5" />
              Grantee
            </h2>
            <div className="text-lg font-semibold text-gray-900">{granteeName}</div>
            {grant.grantee_ein && (
              <div className="text-sm text-gray-600 mt-1">EIN: {grant.grantee_ein}</div>
            )}
            {granteeLocation && (
              <div className="flex items-center gap-2 text-sm text-gray-600 mt-2">
                <MapPinIcon className="h-4 w-4" />
                <span>{granteeLocation}</span>
              </div>
            )}
          </div>
        </div>

        {/* Noncash assistance */}
        {(grant.noncash_assistance_amount != null || grant.noncash_description) && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-3">
              Noncash assistance
            </h2>
            {grant.noncash_assistance_amount != null && (
              <div className="text-sm text-gray-700">
                <span className="font-medium">Amount: </span>
                {formatCurrency(grant.noncash_assistance_amount)}
              </div>
            )}
            {grant.valuation_method && (
              <div className="text-sm text-gray-700 mt-1">
                <span className="font-medium">Valuation method: </span>
                {grant.valuation_method}
              </div>
            )}
            {grant.noncash_description && (
              <p className="text-sm text-gray-700 mt-2 leading-relaxed">
                {grant.noncash_description}
              </p>
            )}
          </div>
        )}

        {/* Source link */}
        {grant.source_url && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <a
              href={grant.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
            >
              <ArrowTopRightOnSquareIcon className="h-5 w-5" />
              View 990 source
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
