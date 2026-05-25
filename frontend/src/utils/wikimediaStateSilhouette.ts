/**
 * State silhouette hero images: Wikimedia Commons cache under
 * `data/cache/wikimedia/` (`{USPS}_silhouette.svg`), copied to
 * `public/wikimedia/` by `scripts/frontend/sync_wikimedia_silhouettes_public.sh`.
 * Map: `src/data/wikimediaStateSilhouettes.json`.
 */
import manifest from '../data/wikimediaStateSilhouettes.json'

type SilhouettesManifest = {
  default_silhouette: string | null
  by_usps: Record<string, string>
}

const m = manifest as SilhouettesManifest

export const WIKIMEDIA_SILHOUETTES_PUBLIC_BASE = '/wikimedia'

export function defaultStateSilhouettePublicSrc(): string | null {
  if (!m.default_silhouette) return null
  return `${WIKIMEDIA_SILHOUETTES_PUBLIC_BASE}/${m.default_silhouette}`
}

/** Commons silhouette SVG for the USPS code when present in the synced cache. */
export function stateSilhouettePublicSrc(stateCode: string | null | undefined): string | null {
  if (!stateCode || stateCode.length !== 2) {
    return defaultStateSilhouettePublicSrc()
  }
  const fn = m.by_usps[stateCode.toUpperCase()]
  if (fn) return `${WIKIMEDIA_SILHOUETTES_PUBLIC_BASE}/${fn}`
  return null
}
