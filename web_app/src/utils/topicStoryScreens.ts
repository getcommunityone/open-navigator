// The screens of a topic story (#1224): the same screen-by-screen format as the Data Center Story, built only from the data
// a topic has. A screen with nothing on record for the place drops out of the story (no segment, not reached by Next), and
// the cover says which ones and why; the Overview and the closing Recap always stay.

export type TopicScreenId = 'overview' | 'timeline' | 'positions' | 'bills' | 'actions' | 'companies' | 'said' | 'decided' | 'recap'

export interface TopicScreen {
  id: TopicScreenId
  /** The screen's short word: the big word, the card, the progress segment's name ("3 of 7: Who spoke"). */
  eyebrow: string
}

export const TOPIC_STORY_SCREENS: TopicScreen[] = [
  { id: 'overview', eyebrow: 'Overview' },
  { id: 'timeline', eyebrow: 'Over time' },
  { id: 'positions', eyebrow: 'Who spoke' },
  { id: 'bills', eyebrow: 'State bills' },
  { id: 'actions', eyebrow: 'Votes' },
  { id: 'companies', eyebrow: 'Companies' },
  { id: 'said', eyebrow: 'What was said' },
  { id: 'decided', eyebrow: 'Decisions' },
  { id: 'recap', eyebrow: 'Recap' },
]

/**
 * What a screen's data is doing: `loading` and `error` keep the screen (it says so itself), `empty` drops it with a note,
 * `absent` drops it silently (the topic has no such data at all, e.g. no companies list).
 */
export type ScreenAvailability = 'loading' | 'error' | 'ready' | 'empty' | 'absent'

/** Why an empty screen is not in the story, for the cover's note ("Not in this story for Ohio: …"). */
const EMPTY_WHY: Record<TopicScreenId, string> = {
  overview: '',
  timeline: 'meetings over time (no meetings on record)',
  positions: "who spoke (the public's position isn't on record yet)",
  bills: 'state bills (none found in our copy of OpenStates)',
  actions: 'votes by local bodies (none in the meetings read)',
  companies: 'companies named (none named in the meetings)',
  said: 'what was said (no quoted passages)',
  decided: 'decisions (none on record)',
  recap: '',
}

export interface TopicScreenPlan {
  screens: TopicScreen[]
  /** The screens left out because the place has nothing on record for them, in story order. */
  dropped: { id: TopicScreenId; why: string }[]
}

/** The screens a topic story shows for one place, from each screen's availability (missing = `loading`). */
export function planTopicScreens(avail: Partial<Record<TopicScreenId, ScreenAvailability>>): TopicScreenPlan {
  const screens: TopicScreen[] = []
  const dropped: TopicScreenPlan['dropped'] = []
  for (const s of TOPIC_STORY_SCREENS) {
    const a = s.id === 'overview' || s.id === 'recap' ? 'ready' : (avail[s.id] ?? 'loading')
    if (a === 'absent') continue
    if (a === 'empty') {
      dropped.push({ id: s.id, why: EMPTY_WHY[s.id] })
      continue
    }
    screens.push(s)
  }
  return { screens, dropped }
}

/** The cover's note on the screens left out, or null when none were: "Not in this story for Ohio: decisions (none on record)." */
export function droppedNote(dropped: TopicScreenPlan['dropped'], label: string): string | null {
  if (dropped.length === 0) return null
  const where = label === 'National' ? 'nationally' : `for ${label}`
  return `Not in this story ${where}: ${dropped.map((d) => d.why).join('; ')}.`
}
