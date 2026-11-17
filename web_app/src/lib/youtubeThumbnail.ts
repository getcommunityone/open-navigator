/**
 * YouTube thumbnails without the Data API (no quota, no key).
 *
 * Every YouTube video exposes its thumbnails as static images on the i.ytimg.com
 * CDN, addressed purely by video id. These are plain image fetches — they do NOT
 * count against the YouTube Data API quota, so they scale to every video we have
 * (we already store `video_id` on every YouTube row). Never call videos.list /
 * search.list just to get a thumbnail.
 *
 * Quality names, in descending resolution:
 *   maxresdefault (1280x720, only if the uploader provided an HD source)
 *   sddefault     (640x480)
 *   hqdefault     (480x360, ALWAYS exists)
 *   mqdefault     (320x180)
 *   default       (120x90)
 *
 * `hqdefault` is the safe default: it is guaranteed to exist for every public
 * video. `maxresdefault` is sharper but 404s on videos without an HD source, so
 * use it only with a runtime fallback (see thumbnailWithFallback).
 */

export type ThumbnailQuality =
  | 'default'
  | 'mqdefault'
  | 'hqdefault'
  | 'sddefault'
  | 'maxresdefault'

/**
 * Static thumbnail URL for a YouTube video id. No API call, no quota.
 * Returns null for an empty/missing id so callers can render an empty state.
 */
export function youtubeThumbnail(
  videoId: string | null | undefined,
  quality: ThumbnailQuality = 'hqdefault',
): string | null {
  if (!videoId) return null
  return `https://i.ytimg.com/vi/${videoId}/${quality}.jpg`
}

/**
 * Ordered candidate URLs, best resolution first. Wire this into an <img> that
 * advances to the next candidate `onError`, so we get the HD thumbnail when it
 * exists and silently fall back to the guaranteed `hqdefault` when it doesn't —
 * still without ever touching the API.
 */
export function youtubeThumbnailCandidates(
  videoId: string | null | undefined,
): string[] {
  if (!videoId) return []
  return [
    `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
    `https://i.ytimg.com/vi/${videoId}/sddefault.jpg`,
    `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
  ]
}

/**
 * YouTube's "video unavailable" placeholder.
 *
 * For a private, removed or still-processing video, i.ytimg.com answers
 * `hqdefault.jpg` with HTTP 200 and a 120x90 grey "…" image (maxres/sd 404).
 * Because it's a 200, `<img onError>` never fires, so the only signal is the
 * decoded size: a real `hqdefault` is 480x360 and a real `sddefault` 640x480.
 * Anything 120px wide or narrower is the placeholder (or a still too small to
 * be worth showing), and we treat it exactly like a 404.
 */
export const YOUTUBE_PLACEHOLDER_MAX_WIDTH = 120

export function isYoutubePlaceholder(img: { naturalWidth: number }): boolean {
  return img.naturalWidth <= YOUTUBE_PLACEHOLDER_MAX_WIDTH
}

/**
 * State of a thumbnail walking its candidate list.
 *  - `idx`: index of the candidate currently in the <img>; `idx >= count` means
 *    every candidate failed (404 or placeholder) → show our fallback.
 *  - `loaded`: the current candidate decoded into a real still.
 */
export interface ThumbnailState {
  idx: number
  loaded: boolean
}

export const INITIAL_THUMBNAIL_STATE: ThumbnailState = { idx: 0, loaded: false }

/** Reducer for an <img> load: a placeholder counts as a miss and advances. */
export function onThumbnailLoad(
  state: ThumbnailState,
  img: { naturalWidth: number },
): ThumbnailState {
  if (isYoutubePlaceholder(img)) return { idx: state.idx + 1, loaded: false }
  return { ...state, loaded: true }
}

/** Reducer for an <img> error (404 etc.): advance to the next candidate. */
export function onThumbnailError(state: ThumbnailState): ThumbnailState {
  return { idx: state.idx + 1, loaded: false }
}

/**
 * Icon family for the "no video preview" cover. Picked from the item's own
 * real text (headline / matched passage) — it only chooses a glyph, it never
 * adds content.
 */
export type ThumbnailKind = 'data-center' | 'zoning' | 'budget' | 'decision' | 'meeting'

export function inferThumbnailKind(
  text: string | null | undefined,
  fallback: ThumbnailKind = 'meeting',
): ThumbnailKind {
  const t = (text || '').toLowerCase()
  if (/data[\s-]?cent(er|re)s?\b|hyperscale|server farm/.test(t)) return 'data-center'
  if (/\b(re)?zon(e|es|ed|ing)\b|land use|annexation|variance|subdivision/.test(t)) return 'zoning'
  if (/budget|appropriat|millage|\btax(es)?\b|levy|bond issue|\bfunding\b|expenditure/.test(t)) return 'budget'
  return fallback
}
