// @ts-nocheck
import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

const geoUrl = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json'

interface BillSample {
  bill_number: string
  title: string
  status: string
  type: string
  action: string
  date?: string  // Format: "Jan 2026"
  state: string
}

interface StateData {
  state: string
  total_bills: number
  type_counts: {
    ban: number
    restriction: number
    protection: number
    other: number
  }
  status_counts: {
    enacted: number
    failed: number
    pending: number
  }
  primary_type: string
  primary_status: string
  map_category: string
  sample_bills?: BillSample[]
}

interface USMapProps {
  stateData: Record<string, StateData>
  onStateClick?: (stateCode: string) => void
  legend?: {
    types: Record<string, string>
    statuses: Record<string, string>
  }
}

// State code to FIPS mapping
const STATE_FIPS: Record<string, string> = {
  'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06',
  'CO': '08', 'CT': '09', 'DE': '10', 'FL': '12', 'GA': '13',
  'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19',
  'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24',
  'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29',
  'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34',
  'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39',
  'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45',
  'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50',
  'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56',
  'DC': '11', 'PR': '72'
}

const FIPS_STATE: Record<string, string> = Object.fromEntries(
  Object.entries(STATE_FIPS).map(([k, v]) => [v, k])
)

// Flexible color palette for different legislation types
const TYPE_COLOR_PALETTE: Record<string, string> = {
  // Fluoridation categories
  'mandate': '#4CAF50',      // Green - Mandate
  'removal': '#F44336',      // Red - Removal
  'study': '#9C27B0',        // Purple - Study
  
  // Dental/Oral Health categories  
  'coverage_expansion': '#4CAF50',  // Green - Expansion
  'screening': '#FF9800',          // Orange - Screening
  'provider_access': '#2196F3',    // Blue - Provider Access
  
  // Medicaid categories
  'expansion': '#4CAF50',     // Green - Expansion
  'coverage': '#2196F3',      // Blue - Coverage
  'reimbursement': '#FF9800', // Orange - Reimbursement
  'eligibility': '#9C27B0',   // Purple - Eligibility
  
  // Education categories
  'requirement': '#FF9800',   // Orange - Requirement
  'curriculum': '#2196F3',    // Blue - Curriculum
  'reform': '#9C27B0',        // Purple - Reform
  
  // Health/General categories
  'protection': '#4CAF50',    // Green - Protection
  'restriction': '#F44336',   // Red - Restriction
  
  // Generic categories
  'support': '#4CAF50',       // Green - Support
  'oppose': '#F44336',        // Red - Oppose
  'regulate': '#FF9800',      // Orange - Regulate
  
  // Shared
  'funding': '#2196F3',       // Blue - Funding (appears in multiple)
  'other': '#9E9E9E',         // Gray - Other
}

// Get color for any category with fallback
const getColorForCategory = (category: string): string => {
  return TYPE_COLOR_PALETTE[category] || '#9E9E9E' // Default to gray
}

// Color scheme based on the user's description
const getStateColor = (stateCode: string, stateData: Record<string, StateData>): string => {
  const data = stateData[stateCode]
  
  // Debug logging for specific states
  if (stateCode === 'MA' || stateCode === '25') {
    console.log('🔍 MA Color Debug:', { stateCode, hasData: !!data, data })
  }
  
  if (!data || data.total_bills === 0) {
    return '#E3F2FD' // Light blue - no legislation
  }
  
  const { primary_type, primary_status } = data
  
  // Get base color for this type
  let baseColor = getColorForCategory(primary_type)
  
  // Adjust shade based on status
  if (primary_status === 'enacted') {
    // Slightly darker for enacted (reduce lightness)
    return adjustColorBrightness(baseColor, -20)
  } else if (primary_status === 'failed') {
    // Lighter for failed (increase lightness)
    return adjustColorBrightness(baseColor, 40)
  }
  
  return baseColor
}

// Helper to adjust color brightness
const adjustColorBrightness = (hex: string, percent: number): string => {
  // Simple brightness adjustment
  const num = parseInt(hex.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = (num >> 16) + amt
  const G = (num >> 8 & 0x00FF) + amt
  const B = (num & 0x0000FF) + amt
  
  return '#' + (
    0x1000000 +
    (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
    (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
    (B < 255 ? (B < 1 ? 0 : B) : 255)
  ).toString(16).slice(1).toUpperCase()
}

const getPatternForState = (stateCode: string, stateData: Record<string, StateData>): string | null => {
  const data = stateData[stateCode]
  
  if (!data || data.total_bills === 0) {
    return null
  }
  
  const { primary_status } = data
  
  if (primary_status === 'failed') {
    return 'crosshatch'
  } else if (primary_status === 'enacted') {
    return 'diagonal'
  }
  
  return null
}

export default function USMap({ stateData, onStateClick, legend }: USMapProps) {
  const [hoveredState, setHoveredState] = useState<string | null>(null)
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 })
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const hoveredStateElementRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // Debug: Log MA data if present
  useEffect(() => {
    if (stateData['MA']) {
      console.log('📊 MA State Data:', stateData['MA'])
    } else {
      console.log('⚠️ No MA data in stateData. Available states:', Object.keys(stateData))
    }
  }, [stateData])
  
  // Get unique types from actual state data if legend not provided
  const legislationTypes = legend?.types || {}
  const legislationStatuses = legend?.statuses || {
    'enacted': 'Enacted',
    'failed': 'Failed', 
    'pending': 'Pending'
  }
  
  // Helper to calculate position relative to container
  const calculateRelativePosition = (element: any) => {
    if (!element || !containerRef.current) return { x: 0, y: 0 }
    
    const stateBounds = element.getBoundingClientRect()
    const containerBounds = containerRef.current.getBoundingClientRect()
    
    return {
      x: stateBounds.left - containerBounds.left + stateBounds.width / 2,
      y: stateBounds.top - containerBounds.top
    }
  }
  
  // Update tooltip position on scroll
  useEffect(() => {
    const updateTooltipPosition = () => {
      if (hoveredState && hoveredStateElementRef.current) {
        setTooltipPosition(calculateRelativePosition(hoveredStateElementRef.current))
      }
    }
    
    if (hoveredState) {
      window.addEventListener('scroll', updateTooltipPosition, true)
      return () => window.removeEventListener('scroll', updateTooltipPosition, true)
    }
  }, [hoveredState])
  
  const handleMouseEnter = (event: any, stateCode: string) => {
    // Clear any pending state change
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
    
    // Store the element reference for scroll updates
    hoveredStateElementRef.current = event.target
    
    // If no tooltip showing, show immediately
    if (!hoveredState) {
      setHoveredState(stateCode)
      setTooltipPosition(calculateRelativePosition(event.target))
    } 
    // If tooltip already showing for different state, delay switch
    // This prevents accidental switches when moving mouse to tooltip
    else if (hoveredState !== stateCode) {
      hoverTimeoutRef.current = setTimeout(() => {
        setHoveredState(stateCode)
        setTooltipPosition(calculateRelativePosition(event.target))
      }, 200) // 200ms delay prevents accidental switches
    }
  }
  
  const handleMouseLeave = () => {
    // Clear any pending state change when leaving
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
  }
  
  // Close button handler
  const handleCloseTooltip = () => {
    setHoveredState(null)
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
  }
  
  const hoveredData = hoveredState ? stateData[hoveredState] : null
  
  return (
    <div ref={containerRef} className="relative">
      {/* SVG Patterns for overlays */}
      <svg width="0" height="0">
        <defs>
          {/* Crosshatch pattern for failed */}
          <pattern id="crosshatch" width="10" height="10" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="10" y2="10" stroke="#000" strokeWidth="1" opacity="0.3" />
            <line x1="10" y1="0" x2="0" y2="10" stroke="#000" strokeWidth="1" opacity="0.3" />
          </pattern>
          
          {/* Diagonal stripes for enacted */}
          <pattern id="diagonal" width="10" height="10" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="10" y2="10" stroke="#000" strokeWidth="2" opacity="0.4" />
          </pattern>
        </defs>
      </svg>
      
      <ComposableMap
        projection="geoAlbersUsa"
        projectionConfig={{
          scale: 1000,
        }}
        className="w-full h-auto"
      >
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const fips = geo.id
              const stateCode = FIPS_STATE[fips] || fips
              const data = stateData[stateCode]
              const pattern = getPatternForState(stateCode, stateData)
              
              // Debug Massachusetts specifically
              if (fips === '25' || stateCode === 'MA') {
                console.log('🗺️ Rendering MA:', { fips, stateCode, hasData: !!data, data })
              }
              
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={pattern ? `url(#${pattern})` : getStateColor(stateCode, stateData)}
                  stroke="#FFFFFF"
                  strokeWidth={0.5}
                  style={{
                    default: {
                      fill: getStateColor(stateCode, stateData),
                      outline: 'none',
                    },
                    hover: {
                      fill: '#607D8B',
                      outline: 'none',
                      cursor: 'pointer',
                    },
                    pressed: {
                      fill: '#455A64',
                      outline: 'none',
                    },
                  }}
                  onClick={() => onStateClick?.(stateCode)}
                  onMouseEnter={(event) => handleMouseEnter(event, stateCode)}
                  onMouseLeave={handleMouseLeave}
                />
              )
            })
          }
        </Geographies>
      </ComposableMap>
      
      {/* Tooltip - Stays visible until hover another state or click close */}
      {hoveredState && hoveredData && (
        <div 
          className="absolute z-50 pointer-events-auto"
          style={{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y - 10}px`,
            transform: 'translate(-50%, -100%)'
          }}
        >
          <div className="bg-gray-900 text-white px-4 py-3 rounded-lg shadow-xl max-w-sm border border-gray-700">
            {/* Close button */}
            <button
              onClick={handleCloseTooltip}
              className="absolute top-2 right-2 text-gray-400 hover:text-white transition-colors"
              aria-label="Close tooltip"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="font-bold text-lg">{STATE_CODE_TO_NAME[hoveredState] || hoveredState}</div>
                <div className="text-xs text-gray-400">{hoveredState}</div>
              </div>
              <div className="text-xs text-gray-400">
                {hoveredData.total_bills.toLocaleString()} bill{hoveredData.total_bills !== 1 ? 's' : ''}
              </div>
            </div>
            
            {hoveredData.total_bills > 0 && (
              <>
                {/* Primary Type and Status - Prominent */}
                <div className="mb-3 p-2 bg-gray-800 rounded-md">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={`
                        w-3 h-3 rounded-full
                        ${hoveredData.primary_type === 'removal' ? 'bg-red-500' : 
                          hoveredData.primary_type === 'mandate' ? 'bg-green-500' :
                          hoveredData.primary_type === 'study' ? 'bg-blue-500' :
                          hoveredData.primary_type === 'funding' ? 'bg-yellow-500' :
                          'bg-gray-500'}
                      `} />
                      <div>
                        <div className="text-sm font-semibold text-white">
                          {legislationTypes[hoveredData.primary_type] || hoveredData.primary_type}
                        </div>
                        <div className="text-xs text-gray-400">Primary Type</div>
                      </div>
                    </div>
                    <div className={`
                      px-2 py-1 rounded text-xs font-medium
                      ${hoveredData.primary_status === 'enacted' ? 'bg-green-500/30 text-green-300 border border-green-500/50' : 
                        hoveredData.primary_status === 'failed' ? 'bg-red-500/30 text-red-300 border border-red-500/50' : 
                        'bg-yellow-500/30 text-yellow-300 border border-yellow-500/50'}
                    `}>
                      {hoveredData.primary_status === 'enacted' ? '✓ Enacted' : 
                       hoveredData.primary_status === 'failed' ? '✗ Failed' : 
                       '⏳ Pending'}
                    </div>
                  </div>
                </div>
                
                {/* Sample Bills Grouped by Type */}
                {hoveredData.sample_bills && hoveredData.sample_bills.length > 0 && (
                  <div className="mb-3 max-h-48 overflow-y-auto">
                    <div className="text-xs font-medium text-gray-300 mb-2">Recent Bills by Type:</div>
                    <div className="space-y-2">
                      {(() => {
                        // Group bills by type
                        const billsByType = hoveredData.sample_bills.reduce((acc, bill) => {
                          if (!acc[bill.type]) acc[bill.type] = []
                          acc[bill.type].push(bill)
                          return acc
                        }, {} as Record<string, BillSample[]>)
                        
                        return Object.entries(billsByType).map(([type, bills]) => (
                          <div key={type} className="bg-gray-800/50 rounded p-2">
                            <div className="flex items-center gap-2 mb-1.5">
                              <div className={`
                                w-2 h-2 rounded-full
                                ${type === 'removal' ? 'bg-red-500' : 
                                  type === 'mandate' ? 'bg-green-500' :
                                  type === 'study' ? 'bg-blue-500' :
                                  type === 'funding' ? 'bg-yellow-500' :
                                  'bg-gray-500'}
                              `} />
                              <div className="text-xs font-medium text-gray-200">
                                {legislationTypes[type] || type} ({bills.length})
                              </div>
                            </div>
                            <div className="space-y-1 ml-4">
                              {bills.map((bill, idx) => (
                                <Link
                                  key={idx}
                                  to={`/bill/${bill.state}-${bill.bill_number}`}
                                  className="block text-xs hover:bg-gray-700/50 rounded px-2 py-1 transition-colors group"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-mono text-blue-300 group-hover:text-blue-200 font-semibold">
                                      {bill.bill_number}
                                    </span>
                                    <span className={`
                                      px-1.5 py-0.5 rounded text-[10px] font-medium
                                      ${bill.status === 'enacted' ? 'bg-green-500/20 text-green-300' : 
                                        bill.status === 'failed' ? 'bg-red-500/20 text-red-300' : 
                                        'bg-yellow-500/20 text-yellow-300'}
                                    `}>
                                      {bill.status === 'enacted' ? '✓ Enacted' : 
                                       bill.status === 'failed' ? '✗ Failed' : '⏳ Pending'}
                                    </span>
                                  </div>
                                  <div className="text-gray-400 text-[10px] mt-0.5 flex items-center gap-1">
                                    {bill.date && <span className="text-gray-500">📅 {bill.date}</span>}
                                    {bill.date && bill.action && <span className="text-gray-600">•</span>}
                                    <span className="flex-1 truncate">{bill.action || 'Click for details'}</span>
                                  </div>
                                </Link>
                              ))}
                            </div>
                          </div>
                        ))
                      })()}
                    </div>
                  </div>
                )}
                
                {/* Status Summary */}
                <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
                  <div className="bg-green-500/10 border border-green-500/30 rounded px-2 py-1.5">
                    <div className="text-green-400 font-bold text-base">{hoveredData.status_counts.enacted}</div>
                    <div className="text-green-300/70">Enacted</div>
                  </div>
                  <div className="bg-yellow-500/10 border border-yellow-500/30 rounded px-2 py-1.5">
                    <div className="text-yellow-400 font-bold text-base">{hoveredData.status_counts.pending}</div>
                    <div className="text-yellow-300/70">Pending</div>
                  </div>
                  <div className="bg-red-500/10 border border-red-500/30 rounded px-2 py-1.5">
                    <div className="text-red-400 font-bold text-base">{hoveredData.status_counts.failed}</div>
                    <div className="text-red-300/70">Failed</div>
                  </div>
                </div>
                
                {/* Drill Down Button */}
                <button
                  onClick={() => onStateClick && onStateClick(hoveredState)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm py-2 px-3 rounded transition-colors flex items-center justify-center gap-2"
                >
                  <span>View All Bills</span>
                  <span className="text-lg">→</span>
                </button>
              </>
            )}
            
            {hoveredData.total_bills === 0 && (
              <div className="text-gray-400 text-sm italic text-center py-2">No legislation found</div>
            )}
            
            {/* Tooltip arrow */}
            <div 
              className="absolute left-1/2 bottom-0 transform -translate-x-1/2 translate-y-full"
              style={{
                width: 0,
                height: 0,
                borderLeft: '8px solid transparent',
                borderRight: '8px solid transparent',
                borderTop: '8px solid rgb(17, 24, 39)'
              }}
            />
          </div>
        </div>
      )}
      
      {/* Legend - Absolute on desktop, below map on mobile */}
      <div className="relative md:absolute md:bottom-4 md:right-4 mt-4 md:mt-0 bg-white/95 rounded-lg shadow-lg p-4 border border-gray-200 max-w-xs mx-auto md:mx-0">
        <div className="text-sm font-semibold text-gray-800 mb-3">Legend</div>
        
        {/* Type of Legislation - Show actual types from data */}
        {(() => {
          // Get unique types from actual state data
          const uniqueTypes = new Set<string>()
          Object.values(stateData).forEach(state => {
            if (state.primary_type) uniqueTypes.add(state.primary_type)
          })
          
          return uniqueTypes.size > 0 && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-600 mb-2">Type of Legislation</div>
              <div className="space-y-1">
                {Array.from(uniqueTypes).sort().map(type => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded flex-shrink-0" style={{ backgroundColor: getColorForCategory(type) }} />
                    <span className="text-xs text-gray-700 capitalize">{legislationTypes[type] || type.replace(/_/g, ' ')}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded flex-shrink-0" style={{ backgroundColor: '#E3F2FD' }} />
                  <span className="text-xs text-gray-700">No Legislation</span>
                </div>
              </div>
            </div>
          )
        })()}
        
        {/* Status of Legislation */}
        <div>
          <div className="text-xs font-medium text-gray-600 mb-2">Status</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border border-gray-300 flex-shrink-0" style={{ backgroundColor: '#666' }} />
              <span className="text-xs text-gray-700">Enacted (darker)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border border-gray-300 flex-shrink-0 bg-white" />
              <span className="text-xs text-gray-700">Pending (normal)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border border-gray-300 flex-shrink-0" style={{ backgroundColor: '#ddd' }} />
              <span className="text-xs text-gray-700">Failed (lighter)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
