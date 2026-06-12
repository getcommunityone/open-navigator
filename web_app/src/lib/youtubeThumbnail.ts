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
