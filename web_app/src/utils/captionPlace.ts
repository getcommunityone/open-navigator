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

function fill(parts: Caption['template'], caption: Caption, topic: string): string {
  return parts.map((p) => (typeof p === 'string' ? p : p.blank === 'place' ? caption.place : topic)).join('')
}

/**
 * The caption split around the place in `scope`, or null when the title doesn't name that place.
 * - The caption's place blank names the scope (a city or state's label, or "America" / "the United States" nationally):
 *   the split is at that blank ("[America ▾] hates data centers.").
 * - Otherwise the title is a broader scope's conclusion ("America hates data centers." at Tuscaloosa, #1222) or names
 *   another place (a national title naming the leading state): null, and the page puts the scope's place control in the
 *   line under the title instead (`splitTextAtPlace` over the subhead, or "Showing [place ▾]"). No "In the United States,"
 *   lead is added to the title (owner, 2026-11-26).
 */
export function splitCaptionAtPlace(caption: Caption, topic: string, scope: StoryScope): CaptionPlaceSplit | null {
  const national = !scope.stateName
  const scopePlace = national ? null : storyScopeLabel(scope)
  const namesScope = national ? NATIONAL_PLACES.includes(caption.place) : caption.place === scopePlace
  const at = caption.template.findIndex((p) => typeof p !== 'string' && p.blank === 'place')
  if (!namesScope || at < 0) return null
  return {
    before: fill(caption.template.slice(0, at), caption, topic),
    place: caption.place,
    after: fill(caption.template.slice(at + 1), caption, topic),
  }
}

/** How the line under the title names the scope when it has to carry the place control. */
export function scopePlaceName(scope: StoryScope): string {
  return scope.stateName ? storyScopeLabel(scope) : 'the United States'
}

/**
 * A line of text split at the first mention of `place` (#1222), for the place control in the subhead when the title
 * names a broader place; null when the line doesn't mention it.
 */
export function splitTextAtPlace(text: string | null | undefined, place: string): CaptionPlaceSplit | null {
  if (!text || !place) return null
  const i = text.indexOf(place)
  if (i < 0) return null
  return { before: text.slice(0, i), place, after: text.slice(i + place.length) }
}
