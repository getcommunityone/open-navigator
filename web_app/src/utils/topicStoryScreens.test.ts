import { describe, expect, it } from 'vitest'
import { droppedNote, planTopicScreens } from './topicStoryScreens'

describe('planTopicScreens (#1224)', () => {
  it('keeps every screen while its data loads, Overview first and Recap last', () => {
    const { screens, dropped } = planTopicScreens({})
    expect(screens.map((s) => s.id)).toEqual(['overview', 'timeline', 'positions', 'companies', 'said', 'decided', 'recap'])
    expect(dropped).toEqual([])
  })
  it('drops an empty screen with a reason and an absent one silently; a failed one stays', () => {
    const { screens, dropped } = planTopicScreens({ timeline: 'ready', positions: 'empty', companies: 'absent', said: 'error', decided: 'empty' })
    expect(screens.map((s) => s.id)).toEqual(['overview', 'timeline', 'said', 'recap'])
    expect(dropped.map((d) => d.id)).toEqual(['positions', 'decided'])
    expect(droppedNote(dropped, 'Ohio')).toBe("Not in this story for Ohio: who spoke (no AI reading of the public's position yet); decisions (none on record).")
  })
  it('says nothing when no screen dropped', () => {
    expect(droppedNote([], 'National')).toBeNull()
  })
})
