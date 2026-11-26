import { HOUSE_THEME } from '../../utils/houseTheme'
import type { Stance } from '../../utils/boxSplit'

/** Box colours: the house theme's segment colours (no red/green pair), a grey for meetings without a stance, the empty tint. */
export const BOX_COLORS: Record<Stance | 'meetings' | 'none', string> = {
  against: HOUSE_THEME.seg[3]!, // muted red
  for: HOUSE_THEME.seg[0]!, // teal
  question: HOUSE_THEME.seg[2]!, // blue
  neutral: HOUSE_THEME.seg[6]!, // plum
  meetings: '#9AA5A9',
  none: HOUSE_THEME.neutral,
}

export const STANCE_LABEL: Record<Stance, string> = {
  against: 'Spoke against',
  for: 'Spoke for',
  question: 'Asked a question',
  neutral: 'No side',
}
