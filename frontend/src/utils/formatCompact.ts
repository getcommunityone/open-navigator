/** Compact human-readable counts (e.g. 16.4k, 1.2M) for dashboard metrics. */

function finite(n: unknown): number | null {
  if (n == null || n === '') return null
  const v = Number(n)
  return Number.isFinite(v) ? v : null
}

/** Full value for tooltips when the display is abbreviated. */
export function formatFullNumber(n: unknown): string | undefined {
  const v = finite(n)
  if (v == null) return undefined
  return v.toLocaleString()
}

export function formatCompactNumber(n: unknown, fallback = '—'): string {
  const v = finite(n)
  if (v == null) return fallback
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs < 1000) return `${sign}${Math.round(abs).toLocaleString()}`
  if (abs >= 1_000_000) {
    const x = abs / 1_000_000
    const body =
      x >= 100
        ? String(Math.round(x))
        : x >= 10
          ? x.toFixed(1).replace(/\.0$/, '')
          : x.toFixed(1).replace(/\.0$/, '')
    return `${sign}${body}M`
  }
  const x = abs / 1000
  const body =
    x >= 100
      ? String(Math.round(x))
      : x >= 10
        ? x.toFixed(1).replace(/\.0$/, '')
        : x.toFixed(1).replace(/\.0$/, '')
  return `${sign}${body}k`
}

export function formatCompactPair(
  a: unknown,
  b: unknown,
  separator = ' / ',
): string {
  return `${formatCompactNumber(a, '?')}${separator}${formatCompactNumber(b, '?')}`
}

/** Hours total (batch transcript duration). */
export function formatCompactHours(hours: unknown): string {
  const h = finite(hours)
  if (h == null) return '—'
  if (h === 0) return '0h'
  if (h < 1000) {
    const rounded = h >= 100 ? Math.round(h) : Math.round(h * 10) / 10
    return `${rounded}h`
  }
  return `${formatCompactNumber(h)}h`
}
