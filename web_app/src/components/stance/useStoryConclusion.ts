import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, nationalLean, speakerStateCount, storyConclusion } from '../../utils/dataStory'
import { speakerCounts } from '../../utils/stanceGame'

/** The national speaker counts with the number of states they were counted in (#1134). */
function nationalCounts(res: Parameters<typeof speakerCounts>[0]) {
  const c = speakerCounts(res)
  return c ? { ...c, states: speakerStateCount(res) } : null
}

/**
 * A story's conclusion headline, gated on the NATIONAL record (#989): the headline speaks for the country, so it is
 * checked against the country's meeting reading or speaker counts (#1134) whatever place the page is scoped to; a page
 * scoped to a place shows the place's own title instead (storyTitle). Null while loading, when the
 * record doesn't back it, or for a story without one.
 */
export function useStoryConclusion(storyId: string) {
  return useStoryConclusionState(storyId).conclusion
}

/**
 * The conclusion and whether the record behind it is still loading, so a page can hold the headline's place instead of
 * flashing the story's question first and then swapping it for the conclusion (#999).
 */
export function useStoryConclusionState(storyId: string) {
  const story = STORIES[storyId]
  const q = useQuery({
    queryKey: ['story-conclusion', 'positions', 'national'],
    queryFn: () => fetchDataCenterPositions({}),
    enabled: Boolean(story?.conclusion),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  return {
    conclusion: story ? storyConclusion(story, nationalCounts(q.data), undefined, nationalLean(q.data)) : null,
    pending: Boolean(story?.conclusion) && q.isPending,
  }
}
