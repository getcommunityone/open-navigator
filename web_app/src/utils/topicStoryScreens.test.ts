import { describe, expect, it } from 'vitest'
import { droppedNote, planTopicScreens } from './topicStoryScreens'

describe('planTopicScreens (#1224)', () => {
  it('keeps every screen while its data loads, Overview first and Recap last', () => {
    const { screens, dropped } = planTopicScreens({})
    expect(screens.map((s) => s.id)).toEqual(['overview', 'upcoming', 'timeline', 'positions', 'bills', 'actions', 'companies', 'said', 'decided', 'recap'])
    expect(dropped).toEqual([])
  })
  it('drops an empty screen with a reason and an absent one silently; a failed one stays', () => {
    const { screens, dropped } = planTopicScreens({ timeline: 'ready', positions: 'empty', bills: 'ready', actions: 'empty', companies: 'absent', said: 'error', decided: 'empty' })
    expect(screens.map((s) => s.id)).toEqual(['overview', 'upcoming', 'timeline', 'bills', 'said', 'recap'])
    expect(dropped.map((d) => d.id)).toEqual(['positions', 'actions', 'decided'])
    expect(droppedNote(dropped, 'Ohio')).toBe(
      "Not in this story for Ohio: who spoke (the public's position isn't on record yet); votes by local bodies (none in the meetings read); decisions (none on record).",
    )
  })
  it('always keeps Coming up (#1302): an empty scope says so on the screen', () => {
    // A stray availability for the screen is ignored: it is never dropped.
    expect(planTopicScreens({ upcoming: 'empty' }).screens.map((s) => s.id)).toContain('upcoming')
  })
  it('says nothing when no screen dropped', () => {
    expect(droppedNote([], 'National')).toBeNull()
  })
})
