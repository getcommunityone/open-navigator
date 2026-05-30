import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import AddressLookup from '../components/AddressLookup'
import { 
  MapPinIcon, 
  UserCircleIcon, 
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'

export default function Settings() {
  const { user } = useAuth()
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

  const API_URL = '/api'  // Vite proxy handles dev routing

  // Update form when user data changes
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

  const handleAddressFound = (location: any) => {
    setLocationData({
      state: location.state,
      county: location.county,
      city: location.city,
      school_board: locationData.school_board, // Keep existing school board
    })
    setUseAddressLookup(false) // Switch back to manual mode after lookup
  }

  const handleChange = (field: string, value: string) => {
    setLocationData(prev => ({ ...prev, [field]: value }))
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
    // Clear save status
    setSaveStatus(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
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
      const response = await fetch(`${API_URL}/auth/profile`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(locationData),
      })

      if (response.ok) {
        setSaveStatus('success')
        // Trigger a page reload to refresh user data (or update context)
        setTimeout(() => window.location.reload(), 1500)
      } else {
        setSaveStatus('error')
      }
    } catch (error) {
      console.error('Failed to update location:', error)
      setSaveStatus('error')
    } finally {
      setIsSaving(false)
    }
  }

  if (!user) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-gray-600">Please sign in to access settings.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold mb-8" style={{ color: '#354F52' }}>
        Settings
      </h1>

      {/* Profile Section */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <UserCircleIcon className="h-6 w-6 text-gray-600" />
            <h2 className="text-xl font-semibold text-gray-900">Profile Information</h2>
          </div>
        </div>
        <div className="px-6 py-4">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="text"
                value={user.email}
                disabled
                className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600"
              />
            </div>
            {user.full_name && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={user.full_name}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600"
                />
              </div>
            )}
            {user.oauth_provider && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Sign-in Method</label>
                <input
                  type="text"
                  value={user.oauth_provider.charAt(0).toUpperCase() + user.oauth_provider.slice(1)}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600 capitalize"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Location Preferences */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <MapPinIcon className="h-6 w-6 text-gray-600" />
            <h2 className="text-xl font-semibold text-gray-900">Location Preferences</h2>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Help us show you relevant local government and nonprofit information
          </p>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4">
          {/* Address Lookup Toggle */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useAddressLookup}
                onChange={(e) => setUseAddressLookup(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm font-medium text-gray-700">
                Use address lookup to auto-fill location
              </span>
            </label>
          </div>

          {/* Address Lookup Section */}
          {useAddressLookup ? (
            <div className="mb-6">
              <AddressLookup onLocationFound={handleAddressFound} />
              <p className="mt-2 text-sm text-gray-500">
                After finding your address, you can review and edit the details below
              </p>
            </div>
          ) : null}

          <div className="space-y-4">
            {/* State */}
            <div>
              <label htmlFor="state" className="block text-sm font-medium text-gray-700 mb-1">
                State <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="state"
                value={locationData.state}
                onChange={(e) => handleChange('state', e.target.value)}
                placeholder="e.g., California, Texas, New York"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.state ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.state && (
                <p className="mt-1 text-sm text-red-600">{errors.state}</p>
              )}
            </div>

            {/* County */}
            <div>
              <label htmlFor="county" className="block text-sm font-medium text-gray-700 mb-1">
                County <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="county"
                value={locationData.county}
                onChange={(e) => handleChange('county', e.target.value)}
                placeholder="e.g., Los Angeles County, Harris County"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.county ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.county && (
                <p className="mt-1 text-sm text-red-600">{errors.county}</p>
              )}
            </div>

            {/* City */}
            <div>
              <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">
                City <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="city"
                value={locationData.city}
                onChange={(e) => handleChange('city', e.target.value)}
                placeholder="e.g., Los Angeles, Houston, New York"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.city ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.city && (
                <p className="mt-1 text-sm text-red-600">{errors.city}</p>
              )}
            </div>

            {/* School Board */}
            <div>
              <label htmlFor="school_board" className="block text-sm font-medium text-gray-700 mb-1">
                School Board / District <span className="text-gray-400 text-xs">(Optional)</span>
              </label>
              <input
                type="text"
                id="school_board"
                value={locationData.school_board}
                onChange={(e) => handleChange('school_board', e.target.value)}
                placeholder="e.g., LAUSD, Houston ISD"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          {/* Save Status */}
          {saveStatus && (
            <div className={`mt-4 p-4 rounded-lg flex items-center gap-2 ${
              saveStatus === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
            }`}>
              {saveStatus === 'success' ? (
                <>
                  <CheckCircleIcon className="h-5 w-5" />
                  <span>Settings saved successfully!</span>
                </>
              ) : (
                <>
                  <ExclamationCircleIcon className="h-5 w-5" />
                  <span>Failed to save settings. Please try again.</span>
                </>
              )}
            </div>
          )}

          {/* Submit Button */}
          <div className="mt-6">
            <button
              type="submit"
              disabled={isSaving}
              className="w-full sm:w-auto px-6 py-2.5 text-white rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: '#354F52' }}
              onMouseEnter={(e) => !isSaving && (e.currentTarget.style.backgroundColor = '#2e4346')}
              onMouseLeave={(e) => !isSaving && (e.currentTarget.style.backgroundColor = '#354F52')}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
