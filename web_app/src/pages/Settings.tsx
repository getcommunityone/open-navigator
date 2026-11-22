/**
 * Settings panel (#674): top-level My account / Site / Admin sections.
 * My account includes profile fields, location, and Following tabs (from Profile).
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import AddressLookup from '../components/AddressLookup'
import SettingsFollowing from '../components/settings/SettingsFollowing'
import {
  MapPinIcon,
  UserCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  XMarkIcon,
  ChartBarSquareIcon,
  WrenchScrewdriverIcon,
  BuildingOffice2Icon,
} from '@heroicons/react/24/outline'
import { tracedFetch } from '../lib/api'
import {
  DATA_EXPLORER_JURISDICTION_QUALITY,
  DATA_EXPLORER_MAP_BASE,
  DATA_EXPLORER_SCORECARD,
} from '../utils/dataExplorerPaths'
import {
  ADMIN_APPLICATION_LINKS,
  ADMIN_BASE,
  ADMIN_BATCH_JOBS,
  ADMIN_LIGHTHOUSE_REPORT,
  ADMIN_MEETING_KINDS,
} from '../utils/adminPaths'

type Section = 'account' | 'site' | 'admin'
type AccountTab = 'profile' | 'location' | 'following'

const DATA_EXPLORER_ENTRY = `${DATA_EXPLORER_MAP_BASE}/us/2024/median_household_income`

function parseSection(raw: string | null, isAdmin: boolean): Section {
  if (raw === 'site') return 'site'
  if (raw === 'admin' && isAdmin) return 'admin'
  // `person` kept as alias for older links
  return 'account'
}

function parseAccountTab(raw: string | null): AccountTab {
  if (raw === 'location' || raw === 'following') return raw
  // `account` kept as alias for the profile fields tab
  return 'profile'
}

export default function Settings() {
  const { user, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const isAdmin = Boolean(user?.is_admin)

  const section = parseSection(searchParams.get('section'), isAdmin)
  const accountTab = parseAccountTab(searchParams.get('tab'))

  const setSection = (s: Section) => {
    const next = new URLSearchParams(searchParams)
    next.set('section', s)
    if (s !== 'account') next.delete('tab')
    else if (!next.get('tab') || next.get('tab') === 'account') next.set('tab', 'profile')
    setSearchParams(next, { replace: true })
  }

  const setAccountTab = (t: AccountTab) => {
    const next = new URLSearchParams(searchParams)
    next.set('section', 'account')
    next.set('tab', t)
    setSearchParams(next, { replace: true })
  }

  const [useAddressLookup, setUseAddressLookup] = useState(false)
  const [locationData, setLocationData] = useState({
    state: user?.state || '',
    county: user?.county || '',
    city: user?.city || '',
    school_board: user?.school_board || '',
  })
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleClose = useCallback(() => {
    if (window.history.length > 1) navigate(-1)
    else navigate('/')
  }, [navigate])

  useEffect(() => {
    if (user) {
      setLocationData({
        state: user.state || '',
        county: user.county || '',
        city: user.city || '',
        school_board: user.school_board || '',
      })
    }
  }, [user])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [handleClose])

  const handleAddressFound = (location: {
    state: string
    county: string
    city: string
  }) => {
    setLocationData((prev) => ({
      ...prev,
      state: location.state,
      county: location.county,
      city: location.city,
    }))
    setUseAddressLookup(false)
  }

  const handleChange = (field: string, value: string) => {
    setLocationData((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
    setSaveStatus(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const newErrors: Record<string, string> = {}
    if (!locationData.state.trim()) newErrors.state = 'State is required'
    if (!locationData.county.trim()) newErrors.county = 'County is required'
    if (!locationData.city.trim()) newErrors.city = 'City is required'
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setIsSaving(true)
    setSaveStatus(null)
    try {
      const token = localStorage.getItem('auth_token')
      const response = await tracedFetch('/api/auth/profile', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(locationData),
      })
      if (response.ok) {
        setSaveStatus('success')
        await refreshUser()
      } else {
        setSaveStatus('error')
      }
    } catch (err) {
      console.error('Failed to update location:', err)
      setSaveStatus('error')
    } finally {
      setIsSaving(false)
    }
  }

  const topTabCls = (active: boolean) =>
    [
      'px-3 py-2 text-sm font-semibold rounded-lg transition-colors',
      active ? 'bg-teal-800 text-white' : 'text-slate-700 hover:bg-slate-100',
    ].join(' ')

  const subTabCls = (active: boolean) =>
    [
      'px-3 py-1.5 text-sm font-medium border-b-2 transition-colors',
      active
        ? 'border-teal-800 text-teal-900'
        : 'border-transparent text-slate-500 hover:text-slate-800',
    ].join(' ')

  const linkCard = (
    title: string,
    blurb: string,
    path: string,
  ) => (
    <button
      type="button"
      key={path}
      onClick={() => {
        handleClose()
        navigate(path)
      }}
      className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left hover:bg-slate-50"
    >
      <span>
        <span className="block text-sm font-medium text-slate-900">{title}</span>
        <span className="block text-xs text-slate-500">{blurb}</span>
      </span>
      <span className="text-xs font-medium text-teal-800">Open</span>
    </button>
  )

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 transition-opacity"
        onClick={handleClose}
        aria-hidden="true"
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-slate-50 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3 sm:px-6">
          <h1 className="text-xl font-bold sm:text-2xl" style={{ color: '#354F52' }}>
            Settings
          </h1>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close settings"
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {!user ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <p className="text-slate-600">Please sign in to access settings.</p>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            {/* Top-level under Settings: My account | Site | Admin */}
            <div
              className="flex flex-wrap gap-2 border-b border-slate-200 bg-white px-5 py-3 sm:px-6"
              role="tablist"
              aria-label="Settings sections"
            >
              <button
                type="button"
                role="tab"
                aria-selected={section === 'account'}
                className={topTabCls(section === 'account')}
                onClick={() => setSection('account')}
              >
                My account
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={section === 'site'}
                className={topTabCls(section === 'site')}
                onClick={() => setSection('site')}
              >
                Site
              </button>
              {isAdmin && (
                <button
                  type="button"
                  role="tab"
                  aria-selected={section === 'admin'}
                  className={topTabCls(section === 'admin')}
                  onClick={() => setSection('admin')}
                >
                  Admin
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6">
              {section === 'account' && (
                <div className="space-y-4">
                  <div className="flex gap-1 border-b border-slate-200" role="tablist" aria-label="My account">
                    <button
                      type="button"
                      className={subTabCls(accountTab === 'profile')}
                      onClick={() => setAccountTab('profile')}
                    >
                      Profile
                    </button>
                    <button
                      type="button"
                      className={subTabCls(accountTab === 'location')}
                      onClick={() => setAccountTab('location')}
                    >
                      Location
                    </button>
                    <button
                      type="button"
                      className={subTabCls(accountTab === 'following')}
                      onClick={() => setAccountTab('following')}
                    >
                      Following
                    </button>
                  </div>

                  {accountTab === 'profile' && (
                    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
                      <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
                        <UserCircleIcon className="h-5 w-5 text-slate-600" />
                        <h2 className="text-base font-semibold text-slate-900">Account</h2>
                      </div>
                      <div className="space-y-3 px-4 py-4">
                        <Field label="Email" value={user.email} />
                        {user.full_name && <Field label="Full name" value={user.full_name} />}
                        {user.oauth_provider && (
                          <Field
                            label="Sign-in method"
                            value={
                              user.oauth_provider.charAt(0).toUpperCase() +
                              user.oauth_provider.slice(1)
                            }
                          />
                        )}
                      </div>
                    </div>
                  )}

                  {accountTab === 'location' && (
                    <form onSubmit={handleSubmit} className="space-y-4">
                      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
                        <div className="border-b border-slate-200 px-4 py-3">
                          <div className="flex items-center gap-2">
                            <MapPinIcon className="h-5 w-5 text-slate-600" />
                            <h2 className="text-base font-semibold text-slate-900">
                              Location preferences
                            </h2>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            Used to show relevant local government and nonprofit information
                          </p>
                        </div>
                        <div className="space-y-4 px-4 py-4">
                          <label className="flex items-center gap-2 rounded-lg bg-slate-50 p-3 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={useAddressLookup}
                              onChange={(e) => setUseAddressLookup(e.target.checked)}
                              className="rounded border-slate-300"
                            />
                            Use address lookup to auto-fill location
                          </label>
                          {useAddressLookup && (
                            <div>
                              <AddressLookup onLocationFound={handleAddressFound} />
                            </div>
                          )}
                          <TextInput
                            id="state"
                            label="State"
                            required
                            value={locationData.state}
                            error={errors.state}
                            onChange={(v) => handleChange('state', v)}
                            placeholder="e.g., California"
                          />
                          <TextInput
                            id="county"
                            label="County"
                            required
                            value={locationData.county}
                            error={errors.county}
                            onChange={(v) => handleChange('county', v)}
                            placeholder="e.g., Los Angeles County"
                          />
                          <TextInput
                            id="city"
                            label="City"
                            required
                            value={locationData.city}
                            error={errors.city}
                            onChange={(v) => handleChange('city', v)}
                            placeholder="e.g., Los Angeles"
                          />
                          <TextInput
                            id="school_board"
                            label="School board / district"
                            value={locationData.school_board}
                            onChange={(v) => handleChange('school_board', v)}
                            placeholder="Optional"
                          />
                          {saveStatus && (
                            <div
                              className={`flex items-center gap-2 rounded-lg p-3 text-sm ${
                                saveStatus === 'success'
                                  ? 'bg-green-50 text-green-800'
                                  : 'bg-red-50 text-red-800'
                              }`}
                            >
                              {saveStatus === 'success' ? (
                                <CheckCircleIcon className="h-5 w-5" />
                              ) : (
                                <ExclamationCircleIcon className="h-5 w-5" />
                              )}
                              <span>
                                {saveStatus === 'success'
                                  ? 'Location saved.'
                                  : 'Failed to save. Please try again.'}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={handleClose}
                          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white"
                        >
                          Close
                        </button>
                        <button
                          type="submit"
                          disabled={isSaving}
                          className="rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                          style={{ backgroundColor: '#354F52' }}
                        >
                          {isSaving ? 'Saving…' : 'Save location'}
                        </button>
                      </div>
                    </form>
                  )}

                  {accountTab === 'following' && (
                    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                      <SettingsFollowing />
                    </div>
                  )}
                </div>
              )}

              {section === 'site' && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-1">
                    <ChartBarSquareIcon className="h-5 w-5 text-slate-600" />
                    <h2 className="text-base font-semibold text-slate-900">Site</h2>
                  </div>
                  <p className="text-sm text-slate-500 mb-2">
                    Maps, scorecards, and data-quality tools for the public site
                  </p>
                  {linkCard(
                    'Data explorer — map',
                    'ACS choropleth and drill-downs',
                    DATA_EXPLORER_ENTRY,
                  )}
                  {linkCard(
                    'Data explorer — scorecard',
                    'Trends and benchmarks',
                    DATA_EXPLORER_SCORECARD,
                  )}
                  {linkCard(
                    'Jurisdiction data quality',
                    'Website / mapping coverage by entity',
                    DATA_EXPLORER_JURISDICTION_QUALITY,
                  )}
                </div>
              )}

              {section === 'admin' && isAdmin && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-1">
                    <WrenchScrewdriverIcon className="h-5 w-5 text-slate-600" />
                    <h2 className="text-base font-semibold text-slate-900">Admin</h2>
                  </div>
                  <p className="text-sm text-slate-500 mb-2">
                    Operational tooling for pipelines and site ops
                  </p>
                  {linkCard('Admin home', 'Lighthouse, batch jobs, and more', ADMIN_BASE)}
                  {linkCard(
                    'Lighthouse report',
                    'Website accessibility / performance scores',
                    ADMIN_LIGHTHOUSE_REPORT,
                  )}
                  {linkCard(
                    'Batch jobs',
                    'Caption / analyze pipeline progress',
                    ADMIN_BATCH_JOBS,
                  )}
                  {linkCard(
                    'Application links',
                    'Data center job-application links',
                    ADMIN_APPLICATION_LINKS,
                  )}
                  {linkCard(
                    'Meeting kinds (not_government)',
                    'Sort by probability and override false skips',
                    ADMIN_MEETING_KINDS,
                  )}
                  <div className="pt-2">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
                      <BuildingOffice2Icon className="h-4 w-4" />
                      Databricks
                    </div>
                    {/* External — leave Settings open; new tab */}
                    <a
                      href="https://adb-7405608833986267.7.azuredatabricks.net"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mb-2 flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left hover:bg-slate-50"
                    >
                      <span>
                        <span className="block text-sm font-medium text-slate-900">
                          Workspace ↗
                        </span>
                      </span>
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input
        type="text"
        value={value}
        disabled
        className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-600"
      />
    </div>
  )
}

function TextInput({
  id,
  label,
  value,
  onChange,
  error,
  required,
  placeholder,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  error?: string
  required?: boolean
  placeholder?: string
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 ${
          error ? 'border-red-500' : 'border-slate-300'
        }`}
      />
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  )
}
