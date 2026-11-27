// The home story title with its place as a control (#1206): the caption from `pickCaption`, split around the place in
// scope so the page can draw that place as the inline place control. Pure, so it is tested. It never changes the
// caption's words; it only says where the place sits in them.
import { storyScopeLabel, type StoryScope } from './dataStory'
import type { Caption } from './storyCaption'

export interface CaptionPlaceSplit {
  /** Text before the place control ("" when the title leads with it). */
  before: string
  /** The place control's text: the place in scope as the caption names it ("America", "Tuscaloosa, Alabama"). */
  place: string
  /** Text after the place control, closing punctuation included. */
  after: string
}

/** How a national caption names the country in its place blank. */
const NATIONAL_PLACES = ['America', 'the United States']
const NATIONAL_LEAD = 'the United States'

function fill(parts: Caption['template'], caption: Caption, topic: string): string {
  return parts.map((p) => (typeof p === 'string' ? p : p.blank === 'place' ? caption.place : topic)).join('')
}

/**
 * The caption split around the place in `scope`.
 * - The caption's place blank names the scope (a city or state's label, or "America" / "the United States" nationally):
 *   the split is at that blank. In a wider-scope title ("America hates data centers; [Tuscaloosa, Alabama] brought them
 *   up in 2 meetings.") that is the place the reader chose, the second place.
 * - Otherwise (a national title naming the leading state, or one with no place blank): "In [the United States], " leads
 *   the caption, so the title still names the scope in effect and stays one sentence.
 */
export function splitCaptionAtPlace(caption: Caption, topic: string, scope: StoryScope): CaptionPlaceSplit {
  const national = !scope.stateName
  const scopePlace = national ? null : storyScopeLabel(scope)
  const namesScope = national ? NATIONAL_PLACES.includes(caption.place) : caption.place === scopePlace
  const at = caption.template.findIndex((p) => typeof p !== 'string' && p.blank === 'place')
  if (namesScope && at >= 0) {
    return {
      before: fill(caption.template.slice(0, at), caption, topic),
      place: caption.place,
      after: fill(caption.template.slice(at + 1), caption, topic),
    }
  }
  const text = fill(caption.template, caption, topic)
  // "In 81 meetings, …" reads "In the United States, in 81 meetings, …"; a sentence led by a name keeps its capital.
  const rest = /^(In|Across) /.test(text) ? text.charAt(0).toLowerCase() + text.slice(1) : text
  return { before: 'In ', place: scopePlace ?? NATIONAL_LEAD, after: `, ${rest}` }
}
