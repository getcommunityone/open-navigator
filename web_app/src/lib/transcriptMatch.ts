/**
 * Locate where a specific decision / bill was discussed inside a meeting
 * transcript, so the UI can offer a "jump to this moment" seek.
 *
 * The AI decision text is a paraphrase, not a verbatim quote, so exact substring
 * search fails. Instead we keyword-match with IDF weighting: words that are rare
 * across this transcript (a proper noun like "lambert", a code like "rsf2") carry
 * far more signal than civic boilerplate ("council", "approved", "motion"), and
 * we reward a tight cluster of distinctive words appearing together.
 */

export interface Cue {
  start: number
  text: string
}

export interface CueMatch {
  /** Seconds to seek the player to. */
  startSeconds: number
  /** Index of the first cue in the matched window. */
  cueIndex: number
  /** Distinct keywords found within the window. */
  keywords: string[]
  /** Cue indices spanned by the matched window (for transcript highlighting). */
  windowIndices: number[]
  /** IDF-weighted score (internal ranking; higher is better). */
  score: number
}

// Common English + civic-meeting boilerplate that carries little locating signal.
const STOPWORDS = new Set([
  'the', 'and', 'for', 'are', 'was', 'were', 'will', 'with', 'that', 'this',
  'from', 'have', 'has', 'had', 'not', 'but', 'all', 'any', 'can', 'her', 'his',
  'our', 'out', 'who', 'its', 'they', 'them', 'then', 'than', 'into', 'over',
  'such', 'also', 'been', 'being', 'their', 'there', 'these', 'those', 'which',
  'while', 'would', 'could', 'should', 'about', 'after', 'before', 'between',
  // civic boilerplate
  'council', 'commission', 'commissioner', 'commissioners', 'board', 'meeting',
  'motion', 'second', 'seconded', 'vote', 'voted', 'approve', 'approved',
  'approval', 'item', 'agenda', 'request', 'requested', 'requesting', 'city',
  'county', 'member', 'members', 'mayor', 'chair', 'clerk', 'staff', 'public',
  'hearing', 'order', 'roll', 'call', 'present', 'aye', 'nay', 'yes',
])

const TOKEN_RE = /[a-z0-9]+/g

/** Tokens worth matching on: content words (len>=4) plus any token with a digit. */
function meaningfulTokens(text: string): string[] {
  const raw = text.toLowerCase().match(TOKEN_RE) || []
  const out: string[] = []
  for (const t of raw) {
    if (STOPWORDS.has(t)) continue
    if (t.length < 4 && !/\d/.test(t)) continue
    out.push(t)
  }
  return out
}

/** Distinct keywords drawn from the decision's headline + statement. */
export function extractKeywords(text: string): string[] {
  return [...new Set(meaningfulTokens(text))]
}

const WINDOW_SECONDS = 30

/**
 * Find the transcript window that best matches `keywords`, or null when no
 * confident match exists. Confidence requires at least two distinct keywords
 * co-located within WINDOW_SECONDS, anchored by at least one distinctive
 * (rare-in-transcript) term — this keeps vague, generic-word-only matches from
 * surfacing a misleading "jump" button.
 */
export function findBestMatch(cues: Cue[], keywords: string[]): CueMatch | null {
  if (cues.length === 0 || keywords.length === 0) return null

  const kwSet = new Set(keywords)

  // Per-cue distinct keyword hits, and document frequency (cues containing each).
  const cueHits: string[][] = []
  const docFreq = new Map<string, number>()
  for (const cue of cues) {
    const found = new Set<string>()
    for (const tok of cue.text.toLowerCase().match(TOKEN_RE) || []) {
      if (kwSet.has(tok)) found.add(tok)
    }
    cueHits.push([...found])
    for (const k of found) docFreq.set(k, (docFreq.get(k) ?? 0) + 1)
  }

  const n = cues.length
  // IDF weight: rare-in-transcript keywords dominate the score.
  const idf = (k: string) => Math.log((n + 1) / ((docFreq.get(k) ?? 0) + 1)) + 1
  // A keyword is a distinctive "anchor" if it occurs in few cues.
  const anchorThreshold = Math.max(2, Math.floor(n * 0.01))
  const isAnchor = (k: string) => (docFreq.get(k) ?? 0) > 0 && (docFreq.get(k) ?? 0) <= anchorThreshold

  let best: CueMatch | null = null

  for (let i = 0; i < n; i++) {
    if (cueHits[i].length === 0) continue // window must open on a hit

    const distinct = new Set<string>()
    const windowIndices: number[] = []
    for (
      let j = i;
      j < n && cues[j].start - cues[i].start <= WINDOW_SECONDS;
      j++
    ) {
      if (cueHits[j].length === 0) continue
      windowIndices.push(j)
      for (const k of cueHits[j]) distinct.add(k)
    }

    if (distinct.size < 2) continue
    if (![...distinct].some(isAnchor)) continue // require a distinctive anchor

    let score = 0
    for (const k of distinct) score += idf(k)

    if (!best || score > best.score) {
      best = {
        startSeconds: cues[i].start,
        cueIndex: i,
        keywords: [...distinct],
        windowIndices,
        score,
      }
    }
  }

  return best
}
