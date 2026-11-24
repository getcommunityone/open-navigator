/** The cue's word: a mouse or trackpad scrolls, a finger swipes (#904). */
export function cueWord(coarsePointer: boolean): 'Scroll' | 'Swipe up' {
  return coarsePointer ? 'Swipe up' : 'Scroll'
}
