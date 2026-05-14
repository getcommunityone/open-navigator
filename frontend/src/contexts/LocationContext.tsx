import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { stateNameToCode } from '../utils/stateMapping'

interface LocationData {
  address?: string
  state: string
  county: string
  city: string
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
  const { user, isAuthenticated } = useAuth()
  const [location, setLocationState] = useState<LocationData | null>(null)

  // Load location from user profile or localStorage (only on initial mount)
  useEffect(() => {
    // Check localStorage first (most recent manual selection)
    const savedLocation = localStorage.getItem('user_location')
    if (savedLocation) {
      try {
        const parsed = JSON.parse(savedLocation)
        
        // Migrate full state names to state codes
        if (parsed.state) {
          parsed.state = stateNameToCode(parsed.state)
        }
        
        setLocationState(parsed)
        
        // Save back the migrated version
        localStorage.setItem('user_location', JSON.stringify(parsed))
        return; // Use localStorage value, don't check user profile
      } catch (e) {
        console.error('Failed to parse saved location:', e)
      }
    }
    
    // If no localStorage, check user profile
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
  }, []) // Empty dependency array - only run on mount

  const setLocation = (newLocation: LocationData) => {
    setLocationState(newLocation)
    
    // Always save to localStorage (even for authenticated users as a backup)
    localStorage.setItem('user_location', JSON.stringify(newLocation))
  }

  const clearLocation = () => {
    setLocationState(null)
    localStorage.removeItem('user_location')
  }

  const hasLocation = location !== null && !!location.state && !!location.city

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
