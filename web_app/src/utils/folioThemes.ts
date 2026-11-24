/**
 * The seven Folio reference themes, as the CSS custom properties the reference defines for each one (index.html, the
 * "Curated Theme Blocks"). They are applied as inline custom properties on the `.folio` root only, so no other page changes.
 * Colours that charts need as plain hex (ramp steps, series) are derived from the same values, so the contrast test in
 * folioRamp.test.ts checks exactly what is drawn.
 */
export type FolioThemeId = 'lavender-press' | 'newsprint' | 'night-edition' | 'gazette-mono' | 'swiss-poster' | 'forest-ochre' | 'riso-pastel'

export interface FolioTheme {
  id: FolioThemeId
  label: string
  dark: boolean
  vars: Record<string, string>
  /** Six sequential steps, lightest (violet-100) to strongest (violet-600). */
  ramp: readonly string[]
  neutral: string
  /** One colour per Census region / quartile group / series (data series A, B, C and a tint). */
  series: readonly string[]
  /** Up to nine part-of-whole segment colours. */
  seg: readonly string[]
}

type Vars = {
  paper: string
  paperRaised: string
  ink: string
  ink2: string
  ink3: string
  rule: string
  band: string
  white: string
  violet: string
  violetInk: string
  vermilion: string
  vermilionInk: string
  magenta: string
  onViolet: string
  onVermilion: string
  onMagenta: string
  v100: string
  v200: string
  v300: string
  v400: string
  v500: string
  v600: string
  vermilionTint: string
  violetTint: string
  neutral: string
}

const make = (id: FolioThemeId, label: string, dark: boolean, v: Vars): FolioTheme => ({
  id,
  label,
  dark,
  vars: {
    '--paper': v.paper,
    '--paper-raised': v.paperRaised,
    '--ink': v.ink,
    '--ink-2': v.ink2,
    '--ink-3': v.ink3,
    '--rule': v.rule,
    '--band': v.band,
    '--white': v.white,
    '--violet': v.violet,
    '--violet-ink': v.violetInk,
    '--vermilion': v.vermilion,
    '--vermilion-ink': v.vermilionInk,
    '--magenta': v.magenta,
    '--on-violet': v.onViolet,
    '--on-vermilion': v.onVermilion,
    '--on-magenta': v.onMagenta,
    '--violet-100': v.v100,
    '--violet-200': v.v200,
    '--violet-300': v.v300,
    '--violet-400': v.v400,
    '--violet-500': v.v500,
    '--violet-600': v.v600,
    '--vermilion-tint': v.vermilionTint,
    '--violet-tint': v.violetTint,
    '--neutral-data': v.neutral,
    colorScheme: dark ? 'dark' : 'light',
  },
  ramp: [v.v100, v.v200, v.v300, v.v400, v.v500, v.v600],
  neutral: v.neutral,
  series: [v.violet, v.vermilion, v.magenta, v.v600],
  seg: [v.violet, v.vermilion, v.magenta, v.v400, v.vermilionInk, v.v300, v.v600, v.vermilionTint, v.neutral],
})

export const FOLIO_THEMES: readonly FolioTheme[] = [
  make('lavender-press', 'Lavender Press', false, {
    paper: '#E8E6EF', paperRaised: '#F4F3F8', ink: '#121116', ink2: '#4A4752', ink3: '#625F6B', rule: '#B8B4C4', band: '#6C50F6', white: '#FFFFFF',
    violet: '#7C63FF', violetInk: '#5A3BE6', vermilion: '#E2492C', vermilionInk: '#B5321A', magenta: '#C04BD9',
    onViolet: '#121116', onVermilion: '#121116', onMagenta: '#121116',
    v100: '#E4DFFC', v200: '#C9BEFB', v300: '#A797FC', v400: '#7C63FF', v500: '#5A3BE6', v600: '#3A22A8',
    vermilionTint: '#F2A391', violetTint: '#B9ABFB', neutral: '#CFCBD9',
  }),
  make('newsprint', 'Newsprint', false, {
    paper: '#F0EADB', paperRaised: '#F8F4EA', ink: '#1A1714', ink2: '#4A4239', ink3: '#655B4F', rule: '#C9BEA9', band: '#1A1714', white: '#F0EADB',
    violet: '#2C4F8C', violetInk: '#2C4F8C', vermilion: '#B23A1E', vermilionInk: '#9E3219', magenta: '#8C6A1C',
    onViolet: '#F8F4EA', onVermilion: '#F8F4EA', onMagenta: '#F8F4EA',
    v100: '#E4E3E0', v200: '#C3CAD6', v300: '#94A5C0', v400: '#6D84AC', v500: '#2C4F8C', v600: '#1B2F57',
    vermilionTint: '#E6AE9C', violetTint: '#A9B8D2', neutral: '#D6CDBB',
  }),
  make('night-edition', 'Night Edition', true, {
    paper: '#121318', paperRaised: '#1C1E25', ink: '#ECEAF2', ink2: '#B9B6C4', ink3: '#9893A3', rule: '#3A3C47', band: '#F2B84B', white: '#121318',
    violet: '#8FA2FF', violetInk: '#A9B6FF', vermilion: '#FF7A59', vermilionInk: '#FF8F73', magenta: '#E58AF0',
    onViolet: '#121318', onVermilion: '#121318', onMagenta: '#121318',
    v100: '#1E2133', v200: '#283063', v300: '#33408A', v400: '#3F52A8', v500: '#8FA2FF', v600: '#C7D0FF',
    vermilionTint: '#6B3A30', violetTint: '#3B437A', neutral: '#3A3C47',
  }),
  make('gazette-mono', 'Gazette Mono', false, {
    paper: '#FFFFFF', paperRaised: '#F4F4F4', ink: '#0A0A0A', ink2: '#3D3D3D', ink3: '#595959', rule: '#BDBDBD', band: '#0A0A0A', white: '#FFFFFF',
    violet: '#4A4A4A', violetInk: '#0A0A0A', vermilion: '#8C8C8C', vermilionInk: '#4A4A4A', magenta: '#6B6B6B',
    onViolet: '#FFFFFF', onVermilion: '#0A0A0A', onMagenta: '#FFFFFF',
    v100: '#F0F0F0', v200: '#D6D6D6', v300: '#B3B3B3', v400: '#8C8C8C', v500: '#4A4A4A', v600: '#1F1F1F',
    vermilionTint: '#CFCFCF', violetTint: '#A6A6A6', neutral: '#E0E0E0',
  }),
  make('swiss-poster', 'Swiss Poster', false, {
    paper: '#F3F1EC', paperRaised: '#FBFAF7', ink: '#111111', ink2: '#3F3F3F', ink3: '#5E5E5E', rule: '#C4C1BA', band: '#D7141A', white: '#FFFFFF',
    violet: '#D7141A', violetInk: '#B5101A', vermilion: '#1E4FD6', vermilionInk: '#1A44B8', magenta: '#808080',
    onViolet: '#FFFFFF', onVermilion: '#FFFFFF', onMagenta: '#111111',
    v100: '#F6E3DF', v200: '#F0BDB5', v300: '#E88A7F', v400: '#E0564C', v500: '#C21218', v600: '#7E0B10',
    vermilionTint: '#B5C6F2', violetTint: '#EFA49C', neutral: '#D9D6CF',
  }),
  make('forest-ochre', 'Forest Ochre', false, {
    paper: '#EAE6D6', paperRaised: '#F4F1E6', ink: '#18201A', ink2: '#3F4A40', ink3: '#58625A', rule: '#BDB89F', band: '#24432E', white: '#F4F1E6',
    violet: '#3B7A4B', violetInk: '#2C6339', vermilion: '#8F5B06', vermilionInk: '#835406', magenta: '#A5432A',
    onViolet: '#F4F1E6', onVermilion: '#F4F1E6', onMagenta: '#F4F1E6',
    v100: '#E3E5D3', v200: '#C3D3B6', v300: '#9DBB92', v400: '#76A06F', v500: '#2F6A3F', v600: '#1B3F26',
    vermilionTint: '#E2C48B', violetTint: '#A9C6A3', neutral: '#D3CDB6',
  }),
  make('riso-pastel', 'Riso Pastel', false, {
    paper: '#F7F2E8', paperRaised: '#FDFAF4', ink: '#22203A', ink2: '#4C4864', ink3: '#625E7A', rule: '#D9CFE0', band: '#D6246E', white: '#FFFFFF',
    violet: '#0074BE', violetInk: '#005E9C', vermilion: '#D6246E', vermilionInk: '#B01A58', magenta: '#007F78',
    onViolet: '#FFFFFF', onVermilion: '#FFFFFF', onMagenta: '#FFFFFF',
    v100: '#EAF1F7', v200: '#CFE3F2', v300: '#A6CDEB', v400: '#6FB0E0', v500: '#0067A8', v600: '#00446F',
    vermilionTint: '#F7B6CF', violetTint: '#B5D8F2', neutral: '#E3DCEB',
  }),
]

export const DEFAULT_THEME_ID: FolioThemeId = 'lavender-press'

/** The theme named by `?theme=`; the default when it is absent or unknown. */
export function themeById(id: string | null | undefined): FolioTheme {
  return FOLIO_THEMES.find((t) => t.id === id) ?? FOLIO_THEMES[0]!
}
