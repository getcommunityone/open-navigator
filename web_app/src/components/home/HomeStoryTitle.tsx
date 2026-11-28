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
  /** The topic word as a dropdown of every live story (#1350); without it the topic is plain text. */
  topicControl?: TopicControl
}

export interface TopicControl {
  /** The current story's slug. */
  value: string
  options: { value: string; label: string }[]
  onPick: (slug: string) => void
}

/**
 * The topic word in a title as the stories' inline dropdown (#1350): the same dotted underline and caret as the place
 * blank, a native select so it is keyboard and screen-reader operable. Sized to the word shown where the browser can.
 */
export function TopicSelect({ word, control }: { word: string; control: TopicControl }) {
  return (
    <span className="home-place home-topic-blank">
      <span className="stance-blank-wrap">
        <select className="stance-blank" aria-label="Topic" value={control.value} onChange={(e) => control.onPick(e.target.value)}>
          {control.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.value === control.value ? word : o.label}
            </option>
          ))}
        </select>
        <span aria-hidden="true" className="stance-blank-caret">
          ▾
        </span>
      </span>
    </span>
  )
}

/** Text with its first mention of the topic word replaced by the topic dropdown (the rest stays text). */
function withTopic(text: string, topic: string, control: TopicControl | undefined, used: { done: boolean }) {
  if (!control || used.done || !topic) return text
  const i = text.toLowerCase().indexOf(topic.toLowerCase())
  if (i < 0) return text
  used.done = true
  return (
    <>
      {text.slice(0, i)}
      <TopicSelect word={text.slice(i, i + topic.length)} control={control} />
      {text.slice(i + topic.length)}
    </>
  )
}

/**
 * The home story title (#1206) with the place in scope as a subtle inline place control ("[America ▾] hates data
 * centers."), the same dialog the story pages use (`PlaceControl`: place search, The United States, All of [state], Use
 * my location, a state list; a bottom sheet on a phone). The words come from the shared caption; this only swaps the
 * place for the control. Without `onPlaceApply` the title is plain text.
 */
export default function HomeStoryTitle({ caption, topic, scope, onPlaceApply, topicControl }: Props) {
  const split = splitCaptionAtPlace(caption, topic, scope)
  // The title names a broader place than the scope (#1222): it stays plain; `HomeStorySubhead` carries the control.
  if (!split) return <>{withTopic(fill(caption, topic), topic, topicControl, { done: false })}</>
  if (!onPlaceApply) return <>{withTopic(`${split.before}${split.place}${split.after}`, topic, topicControl, { done: false })}</>
  return <PlaceSplit split={split} scope={scope} onPlaceApply={onPlaceApply} topic={topic} topicControl={topicControl} />
}

const fill = (caption: Caption, topic: string) =>
  caption.template.map((p) => (typeof p === 'string' ? p : p.blank === 'place' ? caption.place : topic)).join('')

function PlaceSplit({
  split,
  scope,
  onPlaceApply,
  topic = '',
  topicControl,
}: {
  split: CaptionPlaceSplit
  scope: StoryScope
  onPlaceApply: NonNullable<Props['onPlaceApply']>
  topic?: string
  topicControl?: TopicControl
}) {
  const used = { done: false }
  const [open, setOpen] = useState(false)
  const { before, place, after } = split
  // Closing punctuation stays on the control's line, so "." never wraps alone.
  const mark = /^[.?!,;:]/.exec(after)?.[0] ?? ''
  return (
    <>
      {withTopic(before, topic, topicControl, used)}
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
      {withTopic(after.slice(mark.length), topic, topicControl, used)}
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
