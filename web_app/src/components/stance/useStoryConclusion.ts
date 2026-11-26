import { useQuery } from '@tanstack/react-query'
import { fetchDataCenterPositions } from '../../api/dataCenters'
import { STORIES, storyConclusion } from '../../utils/dataStory'
import { speakerCounts } from '../../utils/stanceGame'

/**
 * A story's conclusion headline, gated on the NATIONAL record (#989): the headline speaks for the country, so it is
 * checked against the country's speaker counts whatever place the page is scoped to. Null while loading, when the
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
    conclusion: story ? storyConclusion(story, speakerCounts(q.data)) : null,
    pending: Boolean(story?.conclusion) && q.isPending,
  }
}
