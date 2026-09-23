import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { stateNameToCode } from '../utils/stateMapping'

export type LocationGranularity = 'state' | 'county'

export interface LocationData {
  address?: string
  state: string
  county: string
  city: string
  /** When Nominatim returns a state or county boundary without a city/town. */
  granularity?: LocationGranularity
  school_board?: string
  latitude?: number
  longitude?: number
}

interface LocationContextType {
  location: LocationData | null
  setLocation: (location: LocationData) => void
  clearLocation: () => void
  hasLocation: boolean
}

const LocationContext = createContext<LocationContextType | undefined>(undefined)

export const LocationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth()
  const [location, setLocationState] = useState<LocationData | null>(null)

  // Prefer the most recent manual selection from localStorage. If there is no
  // manual selection, wait for AuthContext's asynchronous /auth/me request and
  // then hydrate from the signed-in user's profile.
  useEffect(() => {
    const savedLocation = localStorage.getItem('user_location')
    if (savedLocation) {
      try {
        const parsed = JSON.parse(savedLocation) as LocationData
        
        // Migrate full state names to state codes
        if (parsed.state) {
          parsed.state = stateNameToCode(parsed.state)
        }
        
        setLocationState(parsed)
        
        // Save back the migrated version
        localStorage.setItem('user_location', JSON.stringify(parsed))
        return // A manual selection takes precedence over the profile.
      } catch (e) {
        console.error('Failed to parse saved location:', e)
        // A corrupt value must not permanently block the profile fallback.
        localStorage.removeItem('user_location')
      }
    }
    
    if (authLoading) return

    if (isAuthenticated && user && user.state && user.city) {
      const stateCode = stateNameToCode(user.state)
      
      const profileLocation = {
        state: stateCode,
        county: user.county || '',
        city: user.city,
        school_board: user.school_board,
      }
      
      setLocationState(profileLocation)
    }
  }, [authLoading, isAuthenticated, user])

  const setLocation = (newLocation: LocationData) => {
    setLocationState(newLocation)
    
    // Always save to localStorage (even for authenticated users as a backup)
    localStorage.setItem('user_location', JSON.stringify(newLocation))
  }

  const clearLocation = () => {
    setLocationState(null)
    localStorage.removeItem('user_location')
  }

  const hasLocation =
    location !== null &&
    !!location.state &&
    (!!location.city ||
      location.granularity === 'state' ||
      (location.granularity === 'county' && !!location.county))

  return (
    <LocationContext.Provider value={{ location, setLocation, clearLocation, hasLocation }}>
      {children}
    </LocationContext.Provider>
  )
}

export const useLocation = () => {
  const context = useContext(LocationContext)
  if (context === undefined) {
    throw new Error('useLocation must be used within a LocationProvider')
  }
  return context
}
