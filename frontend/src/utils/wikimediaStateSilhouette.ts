/**
 * State silhouette hero images: Wikimedia Commons cache under
 * `data/cache/wikimedia/` (`{USPS}_silhouette_locator.svg`, `{USPS}_silhouette_state.svg`,
 * `USA_silhouette.svg` for national default), copied to `public/wikimedia/` by
 * `scripts/frontend/sync_wikimedia_silhouettes_public.sh`.
 * Map: `src/data/wikimediaStateSilhouettes.json`.
 */
import manifest from '../data/wikimediaStateSilhouettes.json'

export type StateSilhouetteVariant = 'locator' | 'state'

type SilhouettesManifest = {
  default_silhouette: string | null
  default_variant?: StateSilhouetteVariant
  by_usps: Record<string, string>
  by_usps_state?: Record<string, string>
  /** Geographic outlines derived from ``USA_silhouette.svg`` (data explorer leaderboard). */
  by_usps_outline?: Record<string, string>
}

const m = manifest as SilhouettesManifest

export const WIKIMEDIA_SILHOUETTES_PUBLIC_BASE = '/wikimedia'

export function defaultStateSilhouettePublicSrc(): string | null {
  if (!m.default_silhouette) return null
  return `${WIKIMEDIA_SILHOUETTES_PUBLIC_BASE}/${m.default_silhouette}`
}

/**
 * Commons silhouette SVG for the USPS code when present in the synced cache.
 * Defaults to the **locator** map (state highlighted on the U.S.), not the standalone outline.
 */
export function stateSilhouettePublicSrc(
  stateCode: string | null | undefined,
  variant: StateSilhouetteVariant = 'locator',
): string | null {
  if (!stateCode || stateCode.length !== 2) {
    return defaultStateSilhouettePublicSrc()
  }
  const usps = stateCode.toUpperCase()
  const fn =
    variant === 'locator'
      ? m.by_usps[usps]
      : m.by_usps_state?.[usps] ?? m.by_usps[usps]
  if (fn) return `${WIKIMEDIA_SILHOUETTES_PUBLIC_BASE}/${fn}`
  return null
}

/**
 * Standalone outline extracted from ``USA_silhouette.svg`` (sync script). Use only when a
 * compact state-only shape is required; most UI should use ``stateSilhouettePublicSrc`` (locator).
 */
export function stateOutlineSilhouettePublicSrc(
  stateCode: string | null | undefined,
): string | null {
  if (!stateCode || stateCode.length !== 2) {
    return defaultStateSilhouettePublicSrc()
  }
  const fn = m.by_usps_outline?.[stateCode.toUpperCase()]
  if (fn) return `${WIKIMEDIA_SILHOUETTES_PUBLIC_BASE}/${fn}`
  return stateSilhouettePublicSrc(stateCode, 'state')
}
