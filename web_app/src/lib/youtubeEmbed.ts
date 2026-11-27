/**
 * YouTube embed URLs for playing a meeting recording in place (#972).
 *
 * The privacy-enhanced host (youtube-nocookie.com) sets no cookies until the viewer plays. The embed is only ever built
 * when the viewer has asked for the video (a click on a meeting dot), so `autoplay=1` starts what they asked for; nothing
 * is fetched from YouTube before that click.
 */

const YT_ID = /^[A-Za-z0-9_-]{11}$/

/** The video id of a YouTube watch / short / embed URL, or null when the URL isn't a YouTube recording. */
export function youtubeVideoId(url: string | null | undefined): string | null {
  if (!url) return null
  let u: URL
  try {
    u = new URL(url)
  } catch {
    return null
  }
  const host = u.hostname.replace(/^www\.|^m\./, '')
  let id: string | null = null
  if (host === 'youtu.be') id = u.pathname.slice(1).split('/')[0] ?? null
  else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    id = u.searchParams.get('v') ?? u.pathname.match(/^\/(?:embed|shorts|live)\/([^/?#]+)/)?.[1] ?? null
  }
  return id && YT_ID.test(id) ? id : null
}

/** The embed URL for `videoId`, starting at `start` seconds (whole seconds; none or negative starts at the beginning). */
export function youtubeEmbedUrl(videoId: string, start?: number | null): string {
  const q = new URLSearchParams({ autoplay: '1', rel: '0', playsinline: '1' })
  if (start != null && Number.isFinite(start) && start > 0) q.set('start', String(Math.floor(start)))
  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${q.toString()}`
}

/**
 * The map hover card's embed (#1277): plays on its own, muted, at `start` seconds, inline on iOS, with YouTube's own controls.
 * The owner asked for this on desktop hover only; the maps never build it on a phone, from keyboard focus, or under reduced
 * motion / data saving. Privacy-enhanced host, as above.
 */
export function youtubeHoverEmbedUrl(videoId: string, start?: number | null): string {
  const s = start != null && Number.isFinite(start) && start > 0 ? `&start=${Math.floor(start)}` : ''
  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?autoplay=1&mute=1${s}&playsinline=1&controls=1&rel=0`
}

/** "1:02:05" / "4:07" for a start time in seconds, for the modal's "from" line. */
export function clockTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}
