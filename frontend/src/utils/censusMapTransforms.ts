/**
 * Scale transforms for choropleth and bubble maps (inspired by d3-in-angular COVID demo).
 * Maps a raw metric value to a display position t ∈ [0, 1] for color and bubble sizing.
 */

export type CensusScaleId = 'linear' | 'sqrt' | 'log' | 'exp'

/**
 * Choropleth fill easing close to D3’s ``easeCubicInOut`` (see d3-in-angular county demos).
 * Use on SVG ``style`` (not the ``fill`` attribute) so the browser can interpolate colors.
 */
export const CENSUS_CHORO_FILL_TRANSITION =
  'fill 1.2s cubic-bezier(0.65, 0, 0.35, 1), stroke 0.45s cubic-bezier(0.65, 0, 0.35, 1)'

/** Robust choropleth range (reduces “flat” maps when a few outliers dominate min/max). */
export function quantileExtent(
  values: (number | null | undefined)[],
  qLow = 0.04,
  qHigh = 0.96,
): { min: number; max: number } {
  const nums = values
    .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    .sort((a, b) => a - b)
  const n = nums.length
  if (n < 2) return { min: 0, max: 1 }
  const lo = nums[Math.max(0, Math.min(n - 1, Math.floor(qLow * (n - 1))))]!
  const hi = nums[Math.max(0, Math.min(n - 1, Math.ceil(qHigh * (n - 1))))]!
  if (!(lo < hi)) {
    const mid = nums[Math.floor(n / 2)]!
    return { min: mid * 0.9, max: mid * 1.1 }
  }
  return { min: lo, max: hi }
}

/** Min/max of observed values (same as ``quantileExtent(..., 0, 1)``). Used for bubble radii so sizes span the full metric range. */
export function minMaxExtent(values: (number | null | undefined)[]): { min: number; max: number } {
  return quantileExtent(values, 0, 1)
}

export const CENSUS_SCALES: { id: CensusScaleId; label: string }[] = [
  { id: 'linear', label: 'Linear' },
  { id: 'sqrt', label: 'Square root' },
  { id: 'log', label: 'Logarithmic' },
  { id: 'exp', label: 'Exponential (t²)' },
]

export function metricToDisplayT(
  v: number | null | undefined,
  min: number,
  max: number,
  scale: CensusScaleId,
): number | null {
  if (v == null || !Number.isFinite(v) || max <= min) return null
  const clamped = Math.max(min, Math.min(max, v))
  const u = (clamped - min) / (max - min)
  switch (scale) {
    case 'linear':
      return u
    case 'sqrt':
      return Math.sqrt(Math.max(0, u))
    case 'log': {
      const lo = Math.log10(Math.max(min, 1))
      const hi = Math.log10(Math.max(max, 1))
      const span = hi - lo || 1e-9
      return (Math.log10(Math.max(clamped, 1)) - lo) / span
    }
    case 'exp':
      return u * u
    default:
      return u
  }
}

/** Multi-stop ramp (readable light end → sky → blue → navy). Low end avoids near-white so fills read on white map panels. */
const CHORO_RGB_STOPS: { t: number; rgb: [number, number, number] }[] = [
  { t: 0, rgb: [196, 208, 231] },
  { t: 0.12, rgb: [206, 218, 244] },
  { t: 0.28, rgb: [191, 219, 254] },
  { t: 0.44, rgb: [125, 211, 252] },
  { t: 0.58, rgb: [56, 189, 248] },
  { t: 0.72, rgb: [59, 130, 246] },
  { t: 0.86, rgb: [29, 78, 216] },
  { t: 1, rgb: [23, 37, 84] },
]

function lerpChannel(a: number, b: number, u: number): number {
  return Math.round(a + (b - a) * u)
}

export function colorFromT(t: number | null): string {
  if (t == null || !Number.isFinite(t)) return '#e2e8f0'
  const x = Math.min(1, Math.max(0, t))
  let i = 0
  while (i < CHORO_RGB_STOPS.length - 2 && x > CHORO_RGB_STOPS[i + 1]!.t) i += 1
  const lo = CHORO_RGB_STOPS[i]!
  const hi = CHORO_RGB_STOPS[i + 1]!
  const span = hi.t - lo.t || 1e-9
  const u = (x - lo.t) / span
  const r = lerpChannel(lo.rgb[0], hi.rgb[0], u)
  const g = lerpChannel(lo.rgb[1], hi.rgb[1], u)
  const b = lerpChannel(lo.rgb[2], hi.rgb[2], u)
  return `rgb(${r},${g},${b})`
}

/**
 * Bubble fill ramp — **Option 1 · Deep Ocean** (boardroom / clinical feel).
 * Steel Blue (low) → Teal (mid) → Deep Emerald (high). Distinct from choropleth fills.
 */
const BUBBLE_BRAND_RGB_STOPS: { t: number; rgb: [number, number, number] }[] = [
  { t: 0, rgb: [44, 110, 138] }, // #2C6E8A Steel Blue
  { t: 0.52, rgb: [42, 157, 143] }, // #2A9D8F Teal
  { t: 1, rgb: [27, 107, 90] }, // #1B6B5A Deep Emerald
]

/** Same interpolation as ``colorFromT`` but using the bubble brand ramp; optional alpha for SVG / canvas. */
export function bubbleFillFromT(t: number | null, alpha = 0.88): string {
  if (t == null || !Number.isFinite(t)) return `rgba(226, 232, 240, ${Math.min(1, alpha + 0.07)})`
  const x = Math.min(1, Math.max(0, t))
  let i = 0
  while (i < BUBBLE_BRAND_RGB_STOPS.length - 2 && x > BUBBLE_BRAND_RGB_STOPS[i + 1]!.t) i += 1
  const lo = BUBBLE_BRAND_RGB_STOPS[i]!
  const hi = BUBBLE_BRAND_RGB_STOPS[i + 1]!
  const span = hi.t - lo.t || 1e-9
  const u = (x - lo.t) / span
  const r = lerpChannel(lo.rgb[0], hi.rgb[0], u)
  const g = lerpChannel(lo.rgb[1], hi.rgb[1], u)
  const b = lerpChannel(lo.rgb[2], hi.rgb[2], u)
  return `rgba(${r},${g},${b},${alpha})`
}

export function bubbleRadiusPx(
  v: number | null | undefined,
  min: number,
  max: number,
  scale: CensusScaleId,
  rMin = 3,
  rMax = 18,
): number {
  const t = metricToDisplayT(v, min, max, scale)
  if (t == null) return rMin
  return rMin + t * (rMax - rMin)
}

/**
 * Compact tick labels for census map bar axes (matches former Recharts XAxis tickFormatter).
 * When ``valueSpan`` is small (Gini, age, rent %), use decimals instead of rounding to 0 / ``k``.
 */
export function formatCensusMapAxisTick(x: number, valueSpan?: number): string {
  const n = Number(x)
  if (!Number.isFinite(n)) return ''
  if (valueSpan != null && Number.isFinite(valueSpan) && valueSpan > 0) {
    if (valueSpan <= 2.5) return n.toFixed(2)
    if (valueSpan <= 120) return n.toFixed(1)
  }
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1000) return `${Math.round(n / 1000)}k`
  return String(Math.round(n))
}

/** Tables / tooltips: ``26 min``, ``1 hr 5 min``. */
export function formatMinutesDisplay(v: number): string {
  if (!Number.isFinite(v)) return '—'
  const sign = v < 0 ? '-' : ''
  const whole = Math.round(Math.abs(v))
  if (whole < 60) return `${sign}${whole} min`
  const h = Math.floor(whole / 60)
  const m = whole % 60
  if (m === 0) return `${sign}${h} hr`
  return `${sign}${h} hr ${m} min`
}

/** Bar ends: ``26m``, ``1h5m``. */
export function formatMinutesCompactDisplay(v: number): string {
  if (!Number.isFinite(v)) return '—'
  const sign = v < 0 ? '-' : ''
  const whole = Math.round(Math.abs(v))
  if (whole < 60) return `${sign}${whole}m`
  const h = Math.floor(whole / 60)
  const m = whole % 60
  return m === 0 ? `${sign}${h}h` : `${sign}${h}h${m}m`
}

/** X-axis ticks when the metric is a duration in minutes (never ``250k``-style magnitudes). */
export function formatCensusMapAxisTickMinutes(x: number, valueSpan?: number): string {
  const n = Number(x)
  if (!Number.isFinite(n)) return ''
  const span = valueSpan != null && Number.isFinite(valueSpan) && valueSpan > 0 ? valueSpan : 30
  if (span <= 4) return `${stripFracZeros(Math.abs(n).toFixed(1))}m`
  const r = Math.round(n)
  if (Math.abs(r) >= 60 && span >= 40) {
    const h = r / 60
    if (Math.abs(h - Math.round(h)) < 0.11) return `${Math.round(h)}h`
    return `${stripFracZeros(h.toFixed(1))}h`
  }
  return `${r}m`
}

export function formatCensusMapAxisTickForMetric(
  slug: string,
  metrics: CensusMetricFormatRow[],
  x: number,
  valueSpan?: number,
): string {
  const m = metrics.find((r) => r.slug === slug)
  if (m?.format === 'minutes' || slug === 'travel_time_to_work_minutes') {
    return formatCensusMapAxisTickMinutes(x, valueSpan)
  }
  return formatCensusMapAxisTick(x, valueSpan)
}

/** Minimal metric row for compact bar-end labels. */
export type CensusMetricFormatRow = { slug: string; format: string }

function stripFracZeros(s: string): string {
  return s.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
}

/** ``$`` / count style compact: 1.2k, 3.4M, 12 (no unit suffix for counts). */
function formatCompactMagnitude(abs: number, withDollar: boolean): string {
  const p = withDollar ? '$' : ''
  if (!(abs > 0) || !Number.isFinite(abs)) return `${p}0`
  if (abs >= 1e9) return `${p}${stripFracZeros((abs / 1e9).toFixed(2))}B`
  if (abs >= 1e6) return `${p}${stripFracZeros((abs / 1e6).toFixed(2))}M`
  if (abs >= 100_000) return `${p}${Math.round(abs / 1000)}k`
  if (abs >= 1000) return `${p}${stripFracZeros((abs / 1000).toFixed(2))}k`
  if (abs >= 100) return `${p}${Math.round(abs)}`
  if (abs >= 10) return `${p}${stripFracZeros(abs.toFixed(1))}`
  if (abs >= 1) return `${p}${stripFracZeros(abs.toFixed(1))}`
  return `${p}${stripFracZeros(abs.toFixed(2))}`
}

/**
 * Short labels for race bar ends: ``$72k``, ``1.2M``, ``4.2%``, ``0.48`` (Gini), ``37.2y``.
 * For ``yoy`` / ``vs_natl`` uses percent with sensible precision.
 */
export function formatMetricValueCompact(
  slug: string,
  v: number,
  metrics: CensusMetricFormatRow[],
  valueMode: 'raw' | 'yoy' | 'vs_natl',
): string {
  if (!Number.isFinite(v)) return '—'
  if (valueMode === 'yoy' || valueMode === 'vs_natl') {
    const a = Math.abs(v)
    const decimals = a >= 10 ? 0 : 1
    return `${v.toFixed(decimals)}%`
  }
  const m = metrics.find((x) => x.slug === slug)
  const f = m?.format ?? ''
  const sign = v < 0 ? '-' : ''
  const av = Math.abs(v)
  if (f === 'minutes' || slug === 'travel_time_to_work_minutes') {
    return formatMinutesCompactDisplay(v)
  }
  if (f === 'currency') return `${sign}${formatCompactMagnitude(av, true)}`
  if (f === 'count') return `${sign}${formatCompactMagnitude(av, false)}`
  if (f === 'percent') return `${stripFracZeros(v.toFixed(1))}%`
  if (f === 'ratio') return stripFracZeros(v.toFixed(3))
  if (f === 'years') return `${stripFracZeros(v.toFixed(1))}y`
  return `${sign}${formatCompactMagnitude(av, false)}`
}
