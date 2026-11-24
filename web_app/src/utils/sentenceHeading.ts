/**
 * Pure helpers for the sentence heading and its inline pickers (issue #883): filtering, grouping, keyboard movement and the
 * "Surprise me" choice. No DOM, so each is unit tested.
 */
export interface PickerOption {
  value: string
  label: string
  /** A small heading to group the option under (for metrics, the bundle's own category, when it has one). */
  group?: string
  /** One line under the label: a unit, or a real figure from the loaded data. Never invented. */
  hint?: string
}

/** Options whose label, group or hint contains every word of the query (case-insensitive). An empty query keeps all. */
export function filterOptions(options: PickerOption[], query: string): PickerOption[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return options
  return options.filter((o) => {
    const hay = `${o.label} ${o.group ?? ''} ${o.hint ?? ''}`.toLowerCase()
    return words.every((w) => hay.includes(w))
  })
}

export interface OptionGroup {
  group: string | null
  items: PickerOption[]
}
/** Consecutive groups in first-seen order; options without a group share one unnamed group, so a flat list is one group. */
export function groupOptions(options: PickerOption[]): OptionGroup[] {
  const out: OptionGroup[] = []
  for (const o of options) {
    const g = o.group ?? null
    let slot = out.find((x) => x.group === g)
    if (!slot) {
      slot = { group: g, items: [] }
      out.push(slot)
    }
    slot.items.push(o)
  }
  return out
}

/** The index after moving `delta` steps in a list of `len`, stopping at the ends ('first' / 'last' jump). -1 when empty. */
export function moveActive(index: number, delta: number | 'first' | 'last', len: number): number {
  if (len <= 0) return -1
  if (delta === 'first') return 0
  if (delta === 'last') return len - 1
  if (index < 0) return delta > 0 ? 0 : len - 1
  return Math.min(len - 1, Math.max(0, index + delta))
}

/** The next option whose label starts with the typed text, searching on from `from` and wrapping; -1 when none. */
export function typeAhead(options: PickerOption[], typed: string, from: number): number {
  const t = typed.toLowerCase()
  if (!t || !options.length) return -1
  for (let k = 0; k < options.length; k++) {
    const i = (Math.max(0, from) + k) % options.length
    if (options[i]!.label.toLowerCase().startsWith(t)) return i
  }
  return -1
}

/** A random candidate other than the current one; null when there is nothing else. `rand` is injectable (0 <= r < 1). */
export function pickRandom<T extends { value: string }>(candidates: T[], currentValue: string, rand: () => number = Math.random): T | null {
  const others = candidates.filter((c) => c.value !== currentValue)
  if (!others.length) return null
  return others[Math.min(others.length - 1, Math.floor(rand() * others.length))]!
}
