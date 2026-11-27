import { useState } from 'react'
import PlaceControl from '../stance/PlaceControl'
import type { StoryScope } from '../../utils/dataStory'
import type { Caption } from '../../utils/storyCaption'
import { scopePlaceName, splitCaptionAtPlace, splitTextAtPlace, type CaptionPlaceSplit } from '../../utils/captionPlace'
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
  const split = splitCaptionAtPlace(caption, topic, scope)
  // The title names a broader place than the scope (#1222): it stays plain; `HomeStorySubhead` carries the control.
  if (!split) return <>{fill(caption, topic)}</>
  if (!onPlaceApply) return <>{`${split.before}${split.place}${split.after}`}</>
  return <PlaceSplit split={split} scope={scope} onPlaceApply={onPlaceApply} />
}

const fill = (caption: Caption, topic: string) =>
  caption.template.map((p) => (typeof p === 'string' ? p : p.blank === 'place' ? caption.place : topic)).join('')

function PlaceSplit({ split, scope, onPlaceApply }: { split: CaptionPlaceSplit; scope: StoryScope; onPlaceApply: NonNullable<Props['onPlaceApply']> }) {
  const [open, setOpen] = useState(false)
  const { before, place, after } = split
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

interface SubheadProps extends Props {
  /** The line under the title (or null). */
  subhead: string | null
  className?: string
}

/**
 * The line under the home title (#1222). When the title names a broader place than the scope ("America hates data
 * centers." at Tuscaloosa), the scope's place control moves here: on the place where the line names it, else as a
 * "Showing [Tuscaloosa, Alabama ▾]" lead. Otherwise the line is plain text.
 */
export function HomeStorySubhead({ caption, topic, scope, onPlaceApply, subhead, className = 'home-story-subhead' }: SubheadProps) {
  const titleHasPlace = splitCaptionAtPlace(caption, topic, scope) != null
  if (titleHasPlace || !onPlaceApply) return subhead ? <p className={className}>{subhead}</p> : null
  const name = scopePlaceName(scope)
  const split = splitTextAtPlace(subhead, name) ?? { before: 'Showing ', place: name, after: subhead ? `. ${subhead}` : '.' }
  return (
    // A div, not a p: the place control's dialog is a div.
    <div className={className} data-testid="home-story-scope-line">
      <PlaceSplit split={split} scope={scope} onPlaceApply={onPlaceApply} />
    </div>
  )
}
