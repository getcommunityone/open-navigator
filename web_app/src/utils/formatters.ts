import { STATE_CODE_TO_NAME } from './stateMapping'

/**
 * Format a number as currency with intelligent units (K, M, B)
 * @param amount - The amount to format
 * @returns Formatted string like "$297.9M" or "$1.2B"
 */
export const formatCurrency = (amount: number | undefined | null): string => {
  if (!amount || amount === 0) return '$0'
  
  const absAmount = Math.abs(amount)
  
  if (absAmount >= 1_000_000_000) {
    return `$${(amount / 1_000_000_000).toFixed(1)}B`
  } else if (absAmount >= 1_000_000) {
    return `$${(amount / 1_000_000).toFixed(1)}M`
  } else if (absAmount >= 1_000) {
    return `$${(amount / 1_000).toFixed(1)}K`
  } else {
    return `$${amount.toFixed(0)}`
  }
}

/**
 * Title-case a city name that often arrives normalized/lowercased from the
 * warehouse (e.g. "boston" -> "Boston", "new york" -> "New York").
 */
export const titleCaseCity = (city: string | undefined | null): string => {
  if (!city) return ''
  return city
    .trim()
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w))
    .join(' ')
}

/**
 * Expand a 2-letter state code to its full name ("MA" -> "Massachusetts").
 * Returns the trimmed input unchanged when it isn't a known code (so an
 * already-full name or unknown value passes through untouched). Use this when
 * the leading label is NOT a city (e.g. a jurisdiction name) and must not be
 * re-cased.
 */
export const expandStateName = (stateCode: string | undefined | null): string => {
  const code = stateCode?.trim().toUpperCase() ?? ''
  return STATE_CODE_TO_NAME[code] ?? stateCode?.trim() ?? ''
}

/**
 * Format a "City, State" location for display: title-cases the (often
 * lowercased) city and expands a 2-letter state code to its full name
 * (e.g. "boston", "MA" -> "Boston, Massachusetts"). Falls back gracefully
 * when either part is missing or the code is unknown.
 */
export const formatCityState = (
  city: string | undefined | null,
  stateCode: string | undefined | null,
): string => {
  return [titleCaseCity(city), expandStateName(stateCode)].filter(Boolean).join(', ')
}

/**
 * Format a number with intelligent units (K, M, B) without currency symbol
 * @param num - The number to format
 * @returns Formatted string like "297.9M" or "1.2B"
 */
export const formatNumber = (num: number | undefined | null): string => {
  if (!num || num === 0) return '0'
  
  const absNum = Math.abs(num)
  
  if (absNum >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1)}B`
  } else if (absNum >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`
  } else if (absNum >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`
  } else {
    return num.toLocaleString()
  }
}
