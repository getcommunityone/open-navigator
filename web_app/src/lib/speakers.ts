// ---------------------------------------------------------------------------
// Voices in the room (human_element) — puts faces to the testimony.
//
// The AI `person_id`/`speaker_id` are descriptive slugs
// (e.g. "chuck_tracy_resident_baldwin_01003"), NOT MDM person ids, so no
// contact photo joins. We derive a display name + role + a deterministic
// initials avatar from the slug — the honest universal fallback that still
// works when a real photo isn't available.
//
// Single source of truth: shared by DecisionDetail's "Voices in the room"
// section and StoryCard's compact "Voices" attribution row.
// ---------------------------------------------------------------------------
export const AVATAR_COLORS = [
  { bg: '#e7f2ef', fg: '#1d6b5f' },
  { bg: '#fdeee7', fg: '#c0432a' },
  { bg: '#eaf1f8', fg: '#2f6fb0' },
  { bg: '#efebfb', fg: '#6b5bd2' },
  { bg: '#fbf3e2', fg: '#9a6b12' },
  { bg: '#fdeef5', fg: '#b03a78' },
]

export const ROLE_WORDS = new Set([
  'resident', 'residents', 'applicant', 'representative', 'rep', 'owner', 'official', 'officials',
  'council', 'councilmember', 'member', 'mayor', 'attorney', 'director', 'chair', 'chairman',
  'chairwoman', 'chairperson', 'president', 'vice', 'spokesperson', 'staff', 'citizen', 'speaker',
  'public', 'commissioner', 'commission', 'developer', 'petitioner', 'neighbor', 'business',
  'manager', 'planner', 'engineer', 'consultant', 'pastor', 'professor', 'teacher', 'student',
  'parent', 'advocate', 'opponent', 'supporter', 'clerk', 'administrator', 'superintendent',
  'sheriff', 'trustee', 'board', 'deputy', 'assistant',
])

export interface Speaker {
  name: string
  role: string
  initials: string
  color: { bg: string; fg: string }
}

export function parseSpeaker(id: string): Speaker {
  const toks = id.split('_').filter(Boolean)
  while (toks.length && /^\d+$/.test(toks[toks.length - 1])) toks.pop() // drop trailing FIPS
  const nameToks = toks.slice(0, 2)
  const lowerName = nameToks.map((t) => t.toLowerCase())
  const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)
  const roleToks = [
    ...new Set(
      toks
        .slice(nameToks.length)
        .map((t) => t.toLowerCase())
        .filter((t) => ROLE_WORDS.has(t) && !lowerName.includes(t)),
    ),
  ]
  const name = nameToks.map(cap).join(' ') || 'Speaker'
  const role = roleToks.map(cap).join(' ')
  const initials = nameToks.map((t) => t.charAt(0).toUpperCase()).join('').slice(0, 2) || '?'
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return { name, role, initials, color: AVATAR_COLORS[h % AVATAR_COLORS.length] }
}
