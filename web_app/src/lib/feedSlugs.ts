// Shared mapping between the personalized-feed backend slugs and the frontend
// StoryLenses tile ids. The backend (api/routes/feed) speaks a different
// vocabulary than the homepage tiles, so we translate at the wire boundary.
//
// Keep these maps in lock-step with:
//   - StoryLenses.tsx  LENSES        (signal tiles: contested/money/flags/soon/next)
//   - StoryLenses.tsx  VALUE_FRAMES  (value-frames: family/faith/charitable/…)
//   - api ALLOWED_SIGNALS / ALLOWED_LENSES

// ---- Signals (StoryLenses LENSES tiles) --------------------------------------
// Backend slug <-> frontend tile id. Backend also allows "slipped-through" and
// "helping-hands", which have NO frontend tile — those are intentionally absent
// here so fromSignalSlug() drops them gracefully when seeding the strip.
const SIGNAL_SLUG_TO_ID: Record<string, string> = {
  contested: 'contested',
  'money-moves': 'money',
  'raised-eyebrows': 'flags',
  'moving-fast': 'soon',
  'watch-next': 'next',
}

const SIGNAL_ID_TO_SLUG: Record<string, string> = Object.fromEntries(
  Object.entries(SIGNAL_SLUG_TO_ID).map(([slug, id]) => [id, slug]),
)

/** Frontend signal tile id -> backend signal slug (e.g. 'money' -> 'money-moves'). */
export function toSignalSlug(id: string): string | undefined {
  return SIGNAL_ID_TO_SLUG[id]
}

/** Backend signal slug -> frontend tile id; `undefined` for unmapped slugs. */
export function fromSignalSlug(slug: string): string | undefined {
  return SIGNAL_SLUG_TO_ID[slug]
}

// ---- Value-frames (StoryLenses VALUE_FRAMES) ---------------------------------
// Backend "lenses" (value-frames) slug <-> frontend value-frame id.
const LENS_SLUG_TO_ID: Record<string, string> = {
  'family-first': 'family',
  'faith-community': 'faith',
  'charitable-impact': 'charitable',
  'neighborhood-life': 'neighborhood',
  education: 'education',
  'local-economy': 'economy',
}

const LENS_ID_TO_SLUG: Record<string, string> = Object.fromEntries(
  Object.entries(LENS_SLUG_TO_ID).map(([slug, id]) => [id, slug]),
)

/** Frontend value-frame id -> backend lens slug (e.g. 'family' -> 'family-first'). */
export function toLensSlug(id: string): string | undefined {
  return LENS_ID_TO_SLUG[id]
}

/** Backend lens slug -> frontend value-frame id; `undefined` for unmapped slugs. */
export function fromLensSlug(slug: string): string | undefined {
  return LENS_SLUG_TO_ID[slug]
}
