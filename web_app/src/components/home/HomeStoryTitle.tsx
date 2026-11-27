import { useState } from 'react'
import PlaceControl from '../stance/PlaceControl'
import type { StoryScope } from '../../utils/dataStory'
import type { Caption } from '../../utils/storyCaption'
import { splitCaptionAtPlace } from '../../utils/captionPlace'
import '../../styles/folio.css'
import '../../styles/stance.css'
import '../../styles/home-place.css'

interface Props {
  /** The caption from `pickCaption` for the page's scope; its words are drawn unchanged. */
  caption: Caption
  /** The topic blank's text ("data centers"). */
  topic: string
  scope: StoryScope
  /** A place picked in the title's control: a state (and city), or null/null for the United States. */
  onPlaceApply?: (stateCode: string | null, city: string | null) => void
}

/**
 * The home story title (#1206) with the place in scope as a subtle inline place control ("[America ▾] hates data
 * centers."), the same dialog the story pages use (`PlaceControl`: place search, The United States, All of [state], Use
 * my location, a state list; a bottom sheet on a phone). The words come from the shared caption; this only swaps the
 * place for the control. Without `onPlaceApply` the title is plain text.
 */
export default function HomeStoryTitle({ caption, topic, scope, onPlaceApply }: Props) {
  const [open, setOpen] = useState(false)
  const { before, place, after } = splitCaptionAtPlace(caption, topic, scope)
  if (!onPlaceApply) return <>{`${before}${place}${after}`}</>
  // Closing punctuation stays on the control's line, so "." never wraps alone.
  const mark = /^[.?!,;:]/.exec(after)?.[0] ?? ''
  return (
    <>
      {before}
      <span className="home-place-nowrap">
        <PlaceControl
          variant="blank"
          themeClassName="home-place"
          display={place}
          stateCode={scope.stateCode ?? undefined}
          city={scope.city ?? null}
          open={open}
          onOpenChange={setOpen}
          onApply={onPlaceApply}
        />
        {mark}
      </span>
      {after.slice(mark.length)}
    </>
  )
}
