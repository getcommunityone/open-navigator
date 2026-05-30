import { useState, useEffect, useRef } from 'react'
import { MapPinIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { nominatimUsStateCode } from '../utils/stateMapping'
import { useLocation as useLocationContext, type LocationData, type LocationGranularity } from '../contexts/LocationContext'

interface AddressLookupProps {
  onLocationFound: (location: LocationData) => void
  initialAddress?: string
  compact?: boolean
}

export default function AddressLookup({ onLocationFound, initialAddress = '', compact = false }: AddressLookupProps) {
  const { clearLocation } = useLocationContext()
  const [address, setAddress] = useState(initialAddress)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<any[]>([])
  const [foundLocation, setFoundLocation] = useState<LocationData | null>(null)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const debounceTimer = useRef<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Fetch suggestions as user types
  const fetchSuggestions = async (query: string) => {
    if (query.trim().length < 3) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    try {
      // Same-origin proxy (api/routes/geocode.py): avoids Nominatim CORS and
      // honors its rate-limit policy server-side.
      const response = await fetch(
        `/api/geocode/search?q=${encodeURIComponent(query)}&limit=5`,
      )

      if (!response.ok) {
        return
      }

      const data = await response.json()

      // Deduplicate results using OSM unique IDs
      const uniqueResults = data.reduce((acc: any[], current: any) => {
        const osmKey = `${current.osm_type}_${current.osm_id}`
        const exists = acc.some((item) => {
          const itemKey = `${item.osm_type}_${item.osm_id}`
          return itemKey === osmKey
        })
        if (!exists) {
          acc.push(current)
        }
        return acc
      }, [])

      setSuggestions(uniqueResults)
      setShowSuggestions(uniqueResults.length > 0)
      setSelectedIndex(-1)
    } catch (err) {
      console.error('Autocomplete error:', err)
    }
  }

  // Handle address input change with debouncing
  const handleAddressChange = (value: string) => {
    setAddress(value)
    setError(null)

    // Clear previous timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
    }

    // Set new timer
    debounceTimer.current = setTimeout(() => {
      fetchSuggestions(value)
    }, 300)
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
    }
  }, [])

  const lookupAddress = async (addressToLookup: string) => {
    if (!addressToLookup.trim()) {
      setError('Please enter an address')
      return
    }

    setIsLoading(true)
    setError(null)
    setSuggestions([])
    setShowSuggestions(false)

    try {
      // Same-origin proxy (api/routes/geocode.py): avoids Nominatim CORS and
      // honors its rate-limit policy server-side.
      const response = await fetch(
        `/api/geocode/search?q=${encodeURIComponent(addressToLookup)}&limit=5`,
      )

      if (!response.ok) {
        throw new Error('Failed to lookup address')
      }

      const data = await response.json()

      if (data.length === 0) {
        setError('Address not found. Please try a different address or be more specific.')
        return
      }

      // Deduplicate results using OSM unique IDs
      const uniqueResults = data.reduce((acc: any[], current: any) => {
        // Use OSM type + ID as unique key (most reliable)
        const osmKey = `${current.osm_type}_${current.osm_id}`
        
        const exists = acc.some((item) => {
          const itemKey = `${item.osm_type}_${item.osm_id}`
          return itemKey === osmKey
        })
        
        if (!exists) {
          acc.push(current)
        }
        return acc
      }, [])

      // If we have multiple unique results, show suggestions
      if (uniqueResults.length > 1) {
        setSuggestions(uniqueResults)
        setShowSuggestions(true)
        return
      }

      // Single result - process it
      processResult(uniqueResults[0])
    } catch (err) {
      console.error('Address lookup error:', err)
      setError('Failed to lookup address. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const processResult = (result: any) => {
    const addr = result.address || {}

    const stateCode = nominatimUsStateCode(addr) || ''
    console.log(`🗺️ [AddressLookup] State from Nominatim address: → "${stateCode}"`)

    const county = (addr.county as string) || ''
    const city =
      (addr.city as string) ||
      (addr.town as string) ||
      (addr.village as string) ||
      (addr.municipality as string) ||
      (addr.hamlet as string) ||
      (addr.suburb as string) ||
      ''

    const hasMunicipality = Boolean(city.trim())
    const hasCounty = Boolean(county.trim())

    let granularity: LocationGranularity | undefined
    if (!hasMunicipality) {
      if (hasCounty) {
        granularity = 'county'
      } else if (
        result.addresstype === 'state' ||
        (stateCode &&
          result.class === 'boundary' &&
          result.type === 'administrative' &&
          result.addresstype !== 'county')
      ) {
        granularity = 'state'
      }
    }

    if (!stateCode) {
      setError('Could not determine a U.S. state from this place. Try a street address or pick a suggestion from the list.')
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    if (!hasMunicipality && !granularity) {
      setError(
        'Could not determine a city or county from this place. Try a street address, city name, or pick a more specific suggestion.'
      )
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    const locationData: LocationData = {
      address: result.display_name,
      state: stateCode,
      county,
      city,
      granularity,
      latitude: parseFloat(result.lat),
      longitude: parseFloat(result.lon),
    }

    console.log('📍 [AddressLookup] Location found:', locationData)
    setSuggestions([])
    setShowSuggestions(false)
    setFoundLocation(locationData)
    onLocationFound(locationData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // If a suggestion is selected, use that
    if (selectedIndex >= 0 && suggestions[selectedIndex]) {
      processResult(suggestions[selectedIndex])
    } else {
      lookupAddress(address)
    }
  }

  const handleSuggestionClick = (suggestion: any) => {
    setAddress(suggestion.display_name)
    processResult(suggestion)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => 
          prev < suggestions.length - 1 ? prev + 1 : prev
        )
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => prev > 0 ? prev - 1 : -1)
        break
      case 'Enter':
        if (selectedIndex >= 0) {
          e.preventDefault()
          processResult(suggestions[selectedIndex])
        }
        break
      case 'Escape':
        setShowSuggestions(false)
        setSelectedIndex(-1)
        break
    }
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser')
      return
    }

    setIsLoading(true)
    setError(null)
    setSuggestions([])

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords

        try {
          // Reverse geocode via same-origin proxy (api/routes/geocode.py).
          const response = await fetch(
            `/api/geocode/reverse?lat=${latitude}&lon=${longitude}`,
          )

          if (!response.ok) {
            throw new Error('Failed to reverse geocode location')
          }

          const data = await response.json()
          
          // Update the address input field
          setAddress(data.display_name)
          
          // Process the result
          processResult(data)
        } catch (err) {
          console.error('Reverse geocoding error:', err)
          setError('Failed to determine your location. Please enter your address manually.')
        } finally {
          setIsLoading(false)
        }
      },
      (error) => {
        console.error('Geolocation error:', error)
        setIsLoading(false)
        
        switch (error.code) {
          case error.PERMISSION_DENIED:
            setError('Location access denied. Please enter your address manually or enable location permissions.')
            break
          case error.POSITION_UNAVAILABLE:
            setError('Location information unavailable. Please enter your address manually.')
            break
          case error.TIMEOUT:
            setError('Location request timed out. Please try again or enter your address manually.')
            break
          default:
            setError('An error occurred while getting your location. Please enter your address manually.')
        }
      },
      {
        enableHighAccuracy: false,  // Use fast network-based location instead of GPS
        timeout: 15000,             // 15 second timeout to allow time for user to grant permission
        maximumAge: 30000           // Allow 30s cached location for faster response
      }
    )
  }

  if (compact) {
    return (
      <form onSubmit={handleSubmit} className="w-full">
        <div className="relative">
          <input
            key="address-input-compact"
            ref={inputRef}
            type="text"
            value={address}
            onChange={(e) => handleAddressChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter your address..."
            className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900"
            disabled={isLoading}
            autoComplete="off"
          />
          <MapPinIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
          <button
            type="submit"
            disabled={isLoading}
            className="absolute right-2 top-1.5 px-3 py-1 text-white rounded-md transition-colors text-sm disabled:opacity-50"
            style={{ backgroundColor: '#354F52' }}
            onMouseEnter={(e) => !isLoading && (e.currentTarget.style.backgroundColor = '#2e4346')}
            onMouseLeave={(e) => !isLoading && (e.currentTarget.style.backgroundColor = '#354F52')}
          >
            {isLoading ? 'Finding...' : 'Find'}
          </button>
          
          {/* Autocomplete suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {suggestions.map((suggestion, index) => {
                const addr = suggestion.address
                const locationName = addr.city || addr.town || addr.village || addr.county || 'Unknown'
                return (
                  <button
                    key={`${suggestion.osm_type}_${suggestion.osm_id}`}
                    type="button"
                    onClick={() => handleSuggestionClick(suggestion)}
                    className={`w-full px-4 py-2 text-left hover:bg-gray-100 transition-colors ${
                      index === selectedIndex ? 'bg-gray-100' : ''
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900">
                      {suggestion.display_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {locationName}, {addr.state}
                    </p>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}
      </form>
    )
  }

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-2">
            <span className="flex items-center gap-2">
              <MapPinIcon className="h-5 w-5" />
              Enter Your Address
            </span>
          </label>
          <div className="relative">
            <input
              key="address-input"
              ref={inputRef}
              type="text"
              id="address"
              name="addresslookup"
              value={address}
              onChange={(e) => handleAddressChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="123 Main St, Los Angeles, CA 90001"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-base text-gray-900"
              disabled={isLoading}
              autoComplete="off"
            />
            
            {/* Autocomplete suggestions dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {suggestions.map((suggestion, index) => {
                  const addr = suggestion.address
                  const locationName = addr.city || addr.town || addr.village || addr.county || 'Unknown'
                  return (
                    <button
                      key={`${suggestion.osm_type}_${suggestion.osm_id}`}
                      type="button"
                      onClick={() => handleSuggestionClick(suggestion)}
                      className={`w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors border-b border-gray-100 last:border-b-0 ${
                        index === selectedIndex ? 'bg-gray-100' : ''
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-900">
                        {suggestion.display_name}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {locationName}, {addr.state}
                      </p>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">
            We'll find your local organizations based on your address
          </p>
          
          {/* Use My Location Button */}
          <div className="mt-3">
            <button
              type="button"
              onClick={useMyLocation}
              disabled={isLoading}
              className="w-full px-4 py-2 bg-white border-2 border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50 hover:border-primary-500 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>{foundLocation ? 'Change My Location' : 'Use My Current Location'}</span>
            </button>
          </div>

          {/* Divider */}
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-2 bg-white text-gray-500">or enter manually</span>
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full px-6 py-3 text-white rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          style={{ backgroundColor: '#354F52' }}
          onMouseEnter={(e) => !isLoading && (e.currentTarget.style.backgroundColor = '#2e4346')}
          onMouseLeave={(e) => !isLoading && (e.currentTarget.style.backgroundColor = '#354F52')}
        >
          {isLoading ? (
            <>
              <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
              <span>Looking up address...</span>
            </>
          ) : (
            <>
              <MagnifyingGlassIcon className="h-5 w-5" />
              <span>Find My Community</span>
            </>
          )}
        </button>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Note: Suggestions now appear as autocomplete dropdown above */}

      {/* Location Results */}
      {foundLocation && !compact && (
        <div className="mt-6 border-2 border-primary-200 rounded-lg overflow-hidden bg-primary-50">
          <div className="bg-primary-600 px-4 py-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <MapPinIcon className="h-5 w-5" />
              Your Local Community
            </h3>
            <button
              onClick={() => window.location.href = '/'}
              className="text-sm text-white hover:text-primary-100 underline font-medium"
            >
              ← Back to Home
            </button>
          </div>
          <div className="p-6 space-y-4">
            <p className="text-sm text-gray-700 mb-4">
              Select a jurisdiction level below to explore organizations, meeting minutes, and contacts:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* City */}
              {foundLocation.city && (
                <button
                  onClick={() => {
                    window.location.href = `/?scope=city`
                  }}
                  className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md hover:border-2 hover:border-blue-500 transition-all text-left w-full group"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition-colors">
                      <svg className="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">City</p>
                      <p className="text-lg font-semibold text-gray-900 mt-1 group-hover:text-blue-600">{foundLocation.city}</p>
                      <p className="text-sm text-gray-600 mt-1">City Council</p>
                      <p className="text-xs text-blue-600 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        Click to explore →
                      </p>
                    </div>
                  </div>
                </button>
              )}

              {/* County */}
              {foundLocation.county && (
                <button
                  onClick={() => {
                    window.location.href = `/?scope=county`
                  }}
                  className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md hover:border-2 hover:border-green-500 transition-all text-left w-full group"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-green-100 rounded-lg group-hover:bg-green-200 transition-colors">
                      <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">County</p>
                      <p className="text-lg font-semibold text-gray-900 mt-1 group-hover:text-green-600">{foundLocation.county}</p>
                      <p className="text-sm text-gray-600 mt-1">County Board</p>
                      <p className="text-xs text-green-600 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        Click to explore →
                      </p>
                    </div>
                  </div>
                </button>
              )}

              {/* State */}
              {foundLocation.state && (
                <button
                  onClick={() => {
                    window.location.href = `/?scope=state`
                  }}
                  className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md hover:border-2 hover:border-purple-500 transition-all text-left w-full group"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-purple-100 rounded-lg group-hover:bg-purple-200 transition-colors">
                      <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">State</p>
                      <p className="text-lg font-semibold text-gray-900 mt-1 group-hover:text-purple-600">{foundLocation.state}</p>
                      <p className="text-sm text-gray-600 mt-1">State Legislature</p>
                      <p className="text-xs text-purple-600 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        Click to explore →
                      </p>
                    </div>
                  </div>
                </button>
              )}

              {/* School District */}
              {foundLocation.city && (
                <button
                  onClick={() => {
                    window.location.href = `/?scope=community`
                  }}
                  className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md hover:border-2 hover:border-amber-500 transition-all text-left w-full group"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-amber-100 rounded-lg group-hover:bg-amber-200 transition-colors">
                      <svg className="h-6 w-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">School District</p>
                      <p className="text-lg font-semibold text-gray-900 mt-1 group-hover:text-amber-600">{foundLocation.city} Unified</p>
                      <p className="text-sm text-gray-600 mt-1">School Board</p>
                      <p className="text-xs text-amber-600 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        Click to explore →
                      </p>
                    </div>
                  </div>
                </button>
              )}
            </div>

            {/* Action Buttons */}
            <div className="pt-4 border-t border-primary-200">
              <p className="text-sm text-gray-600 mb-3">Quick access to all local resources:</p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => {
                    const cityQ = foundLocation.city
                      ? `&city=${encodeURIComponent(foundLocation.city)}`
                      : ''
                    window.location.href = `/documents?state=${foundLocation.state}${cityQ}`
                  }}
                  className="flex-1 min-w-[200px] px-4 py-2 bg-white border-2 border-primary-600 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors font-medium"
                >
                  📄 All Meeting Minutes
                </button>
                <button
                  onClick={() => {
                    const cityQ = foundLocation.city
                      ? `&city=${encodeURIComponent(foundLocation.city)}`
                      : ''
                    window.location.href = `/nonprofits?state=${foundLocation.state}${cityQ}`
                  }}
                  className="flex-1 min-w-[200px] px-4 py-2 bg-white border-2 border-primary-600 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors font-medium"
                >
                  🏢 All Local Organizations
                </button>
              </div>
            </div>

            {/* Start Over */}
            <div className="text-center pt-2">
              <button
                onClick={() => {
                  setFoundLocation(null)
                  setAddress('')
                  setError(null)
                  clearLocation() // Clear the global location context
                }}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium underline"
              >
                Search Different Address
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
