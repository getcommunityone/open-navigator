import React from 'react'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { licensePlatePublicSrc } from '../utils/wikicommonsLicensePlate'

/** Short plate slogans (subset); used only for CSS fallback when no Commons image. */
const STATE_SLOGANS: Partial<Record<string, string>> = {
  AL: 'Heart of Dixie',
  AK: 'North to the Future',
  AZ: 'Grand Canyon State',
  AR: 'Natural State',
  CA: 'The Golden State',
  CO: 'Colorful Colorado',
  CT: 'Constitution State',
  DE: 'The First State',
  FL: 'Sunshine State',
  GA: 'Peach State',
  HI: 'Aloha State',
  ID: 'Gem State',
  IL: 'Land of Lincoln',
  IN: 'Crossroads of America',
  IA: 'Fields of Opportunities',
  KS: 'Ad astra per aspera',
  KY: 'Unbridled Spirit',
  LA: "Sportsman's Paradise",
  ME: 'Vacationland',
  MD: 'America in Miniature',
  MA: 'The Spirit of America',
  MI: 'Great Lakes State',
  MN: 'Land of 10,000 Lakes',
  MS: "Birthplace of America's Music",
  MO: 'Show Me State',
  MT: 'Big Sky Country',
  NE: 'The Good Life',
  NV: 'Battle Born',
  NH: 'Live Free or Die',
  NJ: 'Garden State',
  NM: 'Land of Enchantment',
  NY: 'Empire State',
  NC: 'First in Flight',
  ND: 'Peace Garden State',
  OH: 'Birthplace of Aviation',
  OK: 'Native America',
  OR: 'Pacific Wonderland',
  PA: 'Virtue, Liberty, Independence',
  RI: 'Ocean State',
  SC: 'Smiling Faces, Beautiful Places',
  SD: 'Great Faces, Great Places',
  TN: 'Volunteer State',
  TX: 'Lone Star State',
  UT: 'Life Elevated',
  VT: 'Freedom and Unity',
  VA: 'Virginia is for Lovers',
  WA: 'Evergreen State',
  WV: 'Wild, Wonderful',
  WI: "America's Dairyland",
  WY: 'Forever West',
  DC: 'Taxation Without Representation',
  PR: 'Isla del Encanto',
}

const PLATE_FONT = "'Bebas Neue', sans-serif"
const DEFAULT_SLOGAN = 'Open Navigator'

export type HeroLicensePlateBadgeProps = {
  location: { state: string; county?: string; city?: string } | null
  onChangeLocation: () => void
  changeLocationLabel?: string
}

function plateStateLine(loc: HeroLicensePlateBadgeProps['location']): string {
  if (!loc?.state) return 'United States'
  const code = loc.state.toUpperCase()
  return STATE_CODE_TO_NAME[code] ?? loc.state
}

function plateMainLine(loc: HeroLicensePlateBadgeProps['location']): string {
  if (!loc?.state) return 'Your community'
  const county = loc.county?.replace(/\s+County$/i, '').trim()
  if (county) return truncatePlateText(county, 20)
  const city = loc.city?.trim()
  if (city) return truncatePlateText(city, 20)
  const code = loc.state.toUpperCase()
  return STATE_CODE_TO_NAME[code] ?? loc.state
}

function truncatePlateText(s: string, max: number): string {
  if (s.length <= max) return s
  return `${s.slice(0, Math.max(0, max - 1))}…`
}

function plateSlogan(loc: HeroLicensePlateBadgeProps['location']): string {
  if (!loc?.state) return DEFAULT_SLOGAN
  return STATE_SLOGANS[loc.state.toUpperCase()] ?? DEFAULT_SLOGAN
}

function plateYearLabel(): string {
  return String(new Date().getFullYear())
}

function Bolt({ className }: { className: string }) {
  return (
    <div
      className={`pointer-events-none absolute z-[3] h-1.5 w-1.5 rounded-full ${className}`}
      style={{
        background: 'radial-gradient(circle at 40% 35%, #d0c8b0, #8a8070)',
        boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.4)',
      }}
      aria-hidden
    />
  )
}

type HeroPlateImageProps = {
  src: string
  alt: string
}

/** Plate photo fills the frame; edges crop via cover. Corner bolts render above (z-index). */
function HeroPlateImage({ src, alt }: HeroPlateImageProps) {
  return (
    <div className="relative h-[99px] w-[min(92vw,230px)] min-w-[176px] overflow-hidden rounded-md bg-white">
      <img
        src={src}
        alt={alt}
        decoding="async"
        className="pointer-events-none relative z-0 h-full w-full object-cover object-center select-none"
      />
    </div>
  )
}

type CssFallbackProps = {
  location: HeroLicensePlateBadgeProps['location']
  onActivate: () => void
  onKeyDown: (e: React.KeyboardEvent) => void
  changeLocationLabel: string
}

function CssLicensePlateFallback({
  location,
  onActivate,
  onKeyDown,
  changeLocationLabel,
}: CssFallbackProps) {
  const stateLine = plateStateLine(location)
  const mainLine = plateMainLine(location)
  const slogan = plateSlogan(location)
  const year = plateYearLabel()

  return (
    <div className="group/plate relative mb-1 flex flex-col items-center pb-3 animate-plateIn">
      <div
        role="button"
        tabIndex={0}
        aria-label={changeLocationLabel}
        onClick={onActivate}
        onKeyDown={onKeyDown}
        className="relative inline-flex min-w-[176px] cursor-pointer select-none flex-col items-center rounded-lg border-[3px] border-[#1a3a6b] bg-white px-4 pb-1 pt-1.5 transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:rotate-[0.5deg] hover:shadow-[inset_0_0_0_1px_#d4e8e8,0_8px_28px_rgba(0,0,0,0.22),0_2px_6px_rgba(0,0,0,0.1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b] focus-visible:ring-offset-2"
        style={{
          boxShadow:
            'inset 0 0 0 1px #d4e8e8, 0 4px 18px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.12)',
        }}
      >
        <Bolt className="left-2 top-1.5" />
        <Bolt className="right-2 top-1.5" />
        <Bolt className="bottom-1.5 left-2" />
        <Bolt className="bottom-1.5 right-2" />

        <div
          className="mb-0.5 text-[9px] font-normal uppercase leading-none tracking-[0.25em] text-[#1a3a6b]"
          style={{ fontFamily: PLATE_FONT }}
        >
          {stateLine}
        </div>
        <div className="mb-px text-[7px] leading-none tracking-[3px] text-[#c0392b]" aria-hidden>
          ★ ★ ★
        </div>
        <div
          className="mb-0 max-w-[11.2rem] truncate text-[22px] font-normal uppercase leading-none tracking-[0.12em] text-[#1a3a6b] drop-shadow-[0_1px_0_rgba(255,255,255,0.6)]"
          style={{ fontFamily: PLATE_FONT }}
        >
          {mainLine}
        </div>
        <div
          className="my-0.5 h-[1.5px] w-4/5 bg-gradient-to-r from-transparent via-[#d4e8e8] to-transparent"
          aria-hidden
        />
        <div className="flex items-center gap-2">
          <span
            className="text-[11px] font-normal uppercase leading-none tracking-[0.1em] text-[#c0392b]"
            style={{ fontFamily: PLATE_FONT }}
          >
            {year}
          </span>
          <span className="text-[7px] font-semibold uppercase leading-tight tracking-[0.08em] text-[#1a3a6b]/70">
            {slogan}
          </span>
        </div>
      </div>
      <div
        className="pointer-events-none absolute -bottom-[22px] left-1/2 z-10 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-[#1a6b6b] opacity-0 transition-opacity duration-200 group-hover/plate:opacity-100"
        aria-hidden
      >
        🔄 Change location
      </div>
    </div>
  )
}

function HeroLicensePlateBadge({
  location,
  onChangeLocation,
  changeLocationLabel = 'Change location',
}: HeroLicensePlateBadgeProps) {
  const src = licensePlatePublicSrc(location?.state)
  const alt = !location?.state
    ? 'Sample U.S. state license plate from Wikimedia Commons.'
    : `${location.state} license plate (latest in cache, Wikimedia Commons).`

  const activate = () => {
    onChangeLocation()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      activate()
    }
  }

  if (!src) {
    return (
      <CssLicensePlateFallback
        location={location}
        onActivate={activate}
        onKeyDown={onKeyDown}
        changeLocationLabel={changeLocationLabel}
      />
    )
  }

  return (
    <div className="group/plate relative mb-1 flex flex-col items-center pb-3 animate-plateIn">
      <div
        role="button"
        tabIndex={0}
        aria-label={changeLocationLabel}
        onClick={activate}
        onKeyDown={onKeyDown}
        className="relative cursor-pointer overflow-hidden rounded-lg border-[3px] border-[#1a3a6b] bg-white px-0 py-1 transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:rotate-[0.5deg] hover:shadow-[inset_0_0_0_1px_#d4e8e8,0_8px_28px_rgba(0,0,0,0.22),0_2px_6px_rgba(0,0,0,0.1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b] focus-visible:ring-offset-2"
        style={{
          boxShadow:
            'inset 0 0 0 1px #d4e8e8, 0 4px 18px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.12)',
        }}
      >
        <div className="relative">
          <HeroPlateImage src={src} alt={alt} />
          <Bolt className="left-1.5 top-1.5" />
          <Bolt className="right-1.5 top-1.5" />
          <Bolt className="bottom-1.5 left-1.5" />
          <Bolt className="bottom-1.5 right-1.5" />
        </div>
      </div>
      <div
        className="pointer-events-none absolute -bottom-[22px] left-1/2 z-10 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-[#1a6b6b] opacity-0 transition-opacity duration-200 group-hover/plate:opacity-100"
        aria-hidden
      >
        🔄 Change location
      </div>
    </div>
  )
}

export default HeroLicensePlateBadge
