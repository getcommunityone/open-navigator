import type { ComponentType, SVGProps } from 'react'
import type { HeroPointIcon } from '../../utils/heroPoints'

type Glyph = ComponentType<SVGProps<SVGSVGElement>>

/** Solid quote marks: "Communities are saying no." (#1142, the owner's spec: filled white glyphs on a teal circle). */
function QuoteGlyph(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...props}>
      <path
        fill="currentColor"
        d="M4 18.5v-5.2C4 9.4 5.9 6.6 9.5 5.5l.8 1.7C8.4 8 7.4 9.4 7.2 11.3H10v7.2H4Zm9.6 0v-5.2c0-3.9 1.9-6.7 5.5-7.8l.8 1.7c-1.9.8-2.9 2.2-3.1 4.1h2.8v7.2h-6Z"
      />
    </svg>
  )
}

/** A solid stop octagon with a white bar: "Projects are being stopped." */
function StopGlyph(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...props}>
      <path fill="currentColor" d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2l5.7-5.7Z" />
      <rect x="6.5" y="10.6" width="11" height="2.8" rx="1" fill="var(--hero-point-bg, #0f9d84)" />
    </svg>
  )
}

/** A solid government building: "Officials don't always listen." */
function LandmarkGlyph(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...props}>
      <path
        fill="currentColor"
        d="M12 2.5 21.5 7.6V10h-19V7.6L12 2.5ZM4.5 11.5h3v6.5h-3v-6.5Zm6 0h3v6.5h-3v-6.5Zm6 0h3v6.5h-3v-6.5ZM2.5 19.5h19v2h-19v-2Z"
      />
    </svg>
  )
}

export const HERO_POINT_GLYPHS: Record<HeroPointIcon, Glyph> = {
  quote: QuoteGlyph,
  stop: StopGlyph,
  scale: LandmarkGlyph,
}
