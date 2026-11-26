// The home Browse topics tiles (#1133): which are live, which are guides, which are honestly "coming soon". A tile goes
// live when the topic catalog (`GET /api/topics`) has a curated topic for it with linked meetings, so a topic added later
// goes live with no code change. Pure, so the rule is tested without rendering.
import type { TopicSummary } from '../api/topics'
import { STORIES } from './dataStory'
import { isLiveTopic } from './topicStories'

export type TileStatus = 'live' | 'guide' | 'soon'

export interface TileDecor {
  key: string
  title: string
  blurb: string
  /** Which curated topic makes this tile live: matched on the topic's query slug or name. */
  match?: (t: Pick<TopicSummary, 'query_id' | 'name'>) => boolean
  /** The curated topic whose companies it shows (#1052); absent when none are tracked. */
  companies?: string
  /** Its caption key (utils/storyCaption `CAPTION_COPY`), when it is not the story slug. */
  caption?: string
  /** A published guide the tile links to instead of a story. */
  guide?: string
}

export interface Tile extends TileDecor {
  status: TileStatus
  /** The story it selects (`/stories/<story>`), when live. */
  story?: string
  /** The caption key to read for the page's scope. */
  captionKey: string
}

const slug = (s: string) => (t: Pick<TopicSummary, 'query_id' | 'name'>) => t.query_id === s

/**
 * The owner's order (#1013, #1025): data centers first, then the curated topics we have copy for, then any other live
 * curated topic (most meetings first), then the guides. Flock and license plate readers share one topic (100004), so they
 * are one tile.
 */
export const TILE_DECOR: TileDecor[] = [
  { key: 'dc', title: 'Data centers', blurb: 'Who spoke up, the sites and projects, and what was decided.', match: slug('data-centers'), companies: 'data-centers', caption: 'data-centers' },
  { key: 'str', title: 'Short-term rentals', blurb: 'Airbnb, VRBO and vacation rentals, in the words said at meetings.', match: slug('short-term-rentals'), companies: 'short-term-rentals', caption: 'short-term-rentals' },
  { key: 'lpr', title: 'Flock and license plate readers', blurb: 'Flock Safety cameras, automated plate readers and the contracts behind them.', match: slug('license-plate-readers'), companies: 'license-plate-readers', caption: 'license-plate-readers' },
  { key: 'guns', title: 'Guns', blurb: 'Firearm rules, gun shows and ranges, and gunshot detection, as councils weigh them.', match: slug('guns'), companies: 'guns', caption: 'guns' },
  { key: 'pickleball', title: 'Pickleball', blurb: 'Courts, noise and new venues, as councils and parks boards weigh them.', match: slug('pickleball'), caption: 'pickleball' },
  {
    key: 'bike',
    title: 'Bike lanes',
    blurb: 'Bike lanes and paths, as councils weigh them.',
    match: (t) => /\bbike|bicycl/i.test(`${t.query_id ?? ''} ${t.name}`),
    caption: 'bike-lanes',
  },
  { key: 'fluoride', title: 'Water fluoridation', blurb: 'Whether to keep fluoride in the water, as councils and water boards weigh it.', match: slug('water-fluoridation'), caption: 'water-fluoridation' },
]

export const GUIDE_DECOR: TileDecor[] = [
  // Guides, not meeting stories (#1078, #1079). Insurance stays "coming soon" until #1079 has real data.
  { key: 'nonprofit', title: 'Starting a nonprofit', blurb: 'Every step, filing and fee to start one, with the official source for each.', caption: 'starting-a-nonprofit', guide: '/guides/starting-a-nonprofit' },
  { key: 'insurance', title: 'Insurance shopping', blurb: 'Are you paying too much? What regulators publish, made simple.', caption: 'insurance' },
]

/** The tiles for the catalog. With no catalog (loading or failed) every meeting tile reads "coming soon" except data centers. */
export function buildTiles(topics: TopicSummary[] | null | undefined): Tile[] {
  const live = (topics ?? []).filter(isLiveTopic)
  const used = new Set<string>()
  const tiles: Tile[] = TILE_DECOR.map((d) => {
    const t = live.find((x) => d.match?.(x) && !used.has(x.query_id!))
    if (t) used.add(t.query_id!)
    // Data centers is a registry story (DataStory): live even before the catalog answers.
    const story = t?.query_id ?? (d.key === 'dc' && STORIES['data-centers'] ? 'data-centers' : undefined)
    return { ...d, status: story ? 'live' : 'soon', story, captionKey: d.caption ?? story ?? d.key }
  })
  // Any other live curated topic gets a plain tile of its own (#1128, #1131, #1132 add them).
  const extra = live
    .filter((t) => !used.has(t.query_id!) && !tiles.some((x) => x.story === t.query_id))
    .sort((a, b) => (b.meeting_count ?? 0) - (a.meeting_count ?? 0) || a.name.localeCompare(b.name))
    .map<Tile>((t) => ({
      key: `topic-${t.query_id}`,
      title: t.name,
      blurb: `What local meetings said about ${t.name.toLowerCase()}, in their own words.`,
      status: 'live',
      story: t.query_id!,
      captionKey: t.query_id!,
    }))
  const guides = GUIDE_DECOR.map<Tile>((d) => ({ ...d, status: d.guide ? 'guide' : 'soon', captionKey: d.caption ?? d.key }))
  return [...tiles, ...extra, ...guides]
}
