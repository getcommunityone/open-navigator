// A topic story's four-colour map (#1127): the AI reading of each state's meetings (`topic_meeting_lean`, #1126) in the
// shape the box map splits by. The counts are meetings, not speakers: the public mostly opposed, mostly supported, or split. Meetings
// the AI didn't read stay grey. Pure, so the rule is tested without rendering.

import type { TopicStanceMap } from '../api/topics'
import type { StateStance } from '../components/home/StoryStatesMap'

/**
 * The map's `stance` prop for a topic story.
 * - Not loaded yet, or failed: undefined (the map shows meetings only and claims nothing about a stance).
 * - Loaded, but the topic has no AI reading yet: [] (grey meetings, with the "no AI reading yet" note).
 * - Loaded with a reading: one entry per state that has one; its boxes split against / for / mixed by meeting counts.
 */
export function topicStanceForMap(map: TopicStanceMap | null | undefined): StateStance[] | undefined {
  if (!map) return undefined
  if (!map.available) return []
  return map.by_state
    .filter((s) => s.lean_meetings > 0)
    .map((s) => ({
      state_code: s.state_code,
      meetings: s.meetings,
      speakers_against: Math.max(0, s.public_against_meetings),
      speakers_for: Math.max(0, s.public_for_meetings),
      // Split (#1200): the public spoke but was divided or the reading unsure. Silent meetings stay out of the boxes.
      speakers_neutral: Math.max(0, s.no_side_meetings),
      silent_meetings: Math.max(0, s.silent_meetings ?? 0),
      speakers_question: 0,
      // Public-against is already a band; only the officials-against-the-public outline is carried as a lean count.
      disagreement_meetings: Math.max(0, s.disagreement_meetings),
    }))
}
