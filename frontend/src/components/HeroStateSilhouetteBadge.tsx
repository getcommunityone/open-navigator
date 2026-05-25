import React from 'react'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { stateSilhouettePublicSrc } from '../utils/wikimediaStateSilhouette'

export type HeroStateSilhouetteBadgeProps = {
  location: { state: string; county?: string; city?: string } | null
  onChangeLocation: () => void
  changeLocationLabel?: string
}

function locationLabel(loc: HeroStateSilhouetteBadgeProps['location']): string {
  if (!loc?.state) return 'Your community'
  const county = loc.county?.replace(/\s+County$/i, '').trim()
  if (county) return county
  const city = loc.city?.trim()
  if (city) return city
  const code = loc.state.toUpperCase()
  return STATE_CODE_TO_NAME[code] ?? loc.state
}

function stateName(loc: HeroStateSilhouetteBadgeProps['location']): string {
  if (!loc?.state) return 'United States'
  const code = loc.state.toUpperCase()
  return STATE_CODE_TO_NAME[code] ?? loc.state
}

export default function HeroStateSilhouetteBadge({
  location,
  onChangeLocation,
  changeLocationLabel = 'Change location',
}: HeroStateSilhouetteBadgeProps) {
  const src = stateSilhouettePublicSrc(location?.state)
  const alt = !location?.state
    ? 'Sample U.S. state silhouette from Wikimedia Commons.'
    : `${stateName(location)} state silhouette (Wikimedia Commons).`
  const label = locationLabel(location)
  const state = stateName(location)

  const activate = () => {
    onChangeLocation()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      activate()
    }
  }

  return (
    <div className="group/silhouette relative mb-2 flex flex-col items-center pb-4 animate-[slideUp_0.6s_ease-out]">
      <div
        role="button"
        tabIndex={0}
        aria-label={changeLocationLabel}
        onClick={activate}
        onKeyDown={onKeyDown}
        className="relative flex cursor-pointer flex-col items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-[#52796F] focus-visible:ring-offset-2"
      >
        <div className="flex min-h-[120px] w-[min(220px,70vw)] flex-col items-center justify-end rounded-2xl border border-[#CBD5E1] bg-white/90 px-4 pb-3 pt-4 shadow-[0_8px_24px_rgba(53,79,82,0.12)] transition-[transform,box-shadow] duration-200 group-hover/silhouette:-translate-y-0.5 group-hover/silhouette:shadow-[0_12px_32px_rgba(53,79,82,0.18)]">
          <div className="mb-2 flex h-[88px] w-full items-center justify-center">
            {src ? (
              <img
                src={src}
                alt={alt}
                className="max-h-[88px] max-w-full object-contain opacity-90"
                style={{ filter: 'drop-shadow(0 2px 4px rgba(53,79,82,0.15))' }}
              />
            ) : (
              <div
                className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-gradient-to-br from-[#E8EEF2] to-[#CBD5E1] text-2xl"
                aria-hidden
              >
                🗺️
              </div>
            )}
          </div>
          <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#84A98C]">{state}</p>
          <p className="text-sm font-medium text-[#354F52]">{label}</p>
        </div>
      </div>
      <div
        className="pointer-events-none absolute -bottom-6 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-[#52796F] opacity-0 transition-opacity duration-200 group-hover/silhouette:opacity-100"
        aria-hidden
      >
        Change location
      </div>
    </div>
  )
}
