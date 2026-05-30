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
