/**
 * License plate hero images: Wikimedia Commons cache exported under
 * `data/cache/wikicommons/` (`{USPS}_latest.{jpg,png,webp}`), copied to
 * `public/wikicommons/` by `scripts/frontend/sync_wikicommons_plates_public.sh`.
 * Map: `src/data/wikicommonsPlatesLatest.json`.
 */
import manifest from '../data/wikicommonsPlatesLatest.json'

type PlatesManifest = {
  default_plate: string | null
  by_usps: Record<string, string>
}

const m = manifest as PlatesManifest

export const WIKICOMMONS_PLATES_PUBLIC_BASE = '/wikicommons'

export function defaultLicensePlatePublicSrc(): string | null {
  if (!m.default_plate) return null
  return `${WIKICOMMONS_PLATES_PUBLIC_BASE}/${m.default_plate}`
}

/** Latest Commons plate for the USPS code when present in the cache; otherwise default sample plate. */
export function licensePlatePublicSrc(stateCode: string | null | undefined): string | null {
  const fallback = defaultLicensePlatePublicSrc()
  if (!fallback) return null
  if (stateCode && stateCode.length === 2) {
    const fn = m.by_usps[stateCode.toUpperCase()]
    if (fn) return `${WIKICOMMONS_PLATES_PUBLIC_BASE}/${fn}`
  }
  return fallback
}
