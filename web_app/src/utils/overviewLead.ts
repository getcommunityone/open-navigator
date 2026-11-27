// The topic story Overview's left column (#1349): its headline already says "Where {topic} came up in {place}.", so the
// subhead and lede under it are kept only when they add something. Owner feedback (27 Nov 2026): the column said nearly
// the same sentence three times ("Where water fluoridation came up in Alabama.", "Where water fluoridation came up at
// local meetings in Alabama, in the words said there." and "What local governments said about water fluoridation, in the
// words said at the meeting.").

/** The generic lede `topicStories.ts` gives a topic without its own copy: it restates the headline. */
const GENERIC_LEDE = /^What local governments said about .+, in the words said at the meeting\.$/
/** The subhead `captionSubhead` gives a volume / state-gap caption: "Where {topic} came up at local meetings…". */
const WHERE_SUBHEAD = /^Where .+ came up\b/

export interface OverviewLead {
  subhead: string | null
  lede: string | null
}

/** The subhead and lede to show under the Overview headline: a line that only restates "where it came up" is dropped. */
export function overviewLead(subhead: string | null | undefined, lede: string | null | undefined): OverviewLead {
  const s = (subhead ?? '').trim()
  const l = (lede ?? '').trim()
  return {
    subhead: s && !WHERE_SUBHEAD.test(s) ? s : null,
    lede: l && !GENERIC_LEDE.test(l) ? l : null,
  }
}
