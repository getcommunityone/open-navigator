// The anonymous player id: a random UUID kept in localStorage. Nothing else about the player is stored.
const KEY = 'on_stance_player_id'
let memoryId: string | null = null

function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // Older browsers only: RFC 4122 v4 from getRandomValues.
  const b = new Uint8Array(16)
  crypto.getRandomValues(b)
  b[6] = (b[6]! & 0x0f) | 0x40
  b[8] = (b[8]! & 0x3f) | 0x80
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

/** The stored id, made on first use. Falls back to an in-memory id when storage is blocked. */
export function getStancePlayerId(): string {
  if (memoryId) return memoryId
  try {
    const stored = window.localStorage.getItem(KEY)
    if (stored && /^[0-9a-f-]{36}$/i.test(stored)) {
      memoryId = stored
      return stored
    }
    const fresh = makeId()
    window.localStorage.setItem(KEY, fresh)
    memoryId = fresh
    return fresh
  } catch {
    memoryId = memoryId ?? makeId()
    return memoryId
  }
}
