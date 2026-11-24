import { useRef } from 'react'

/**
 * The page writes the screen in view into the URL (replace) while the reader scrolls. When a fast scroll passes several
 * screens, the URL a render sees can lag the last value written, and that must not read as "the address changed from
 * outside" and drag the page back. This remembers what the page itself wrote in the last couple of seconds.
 */
export function useRecentWrites(ttlMs = 2500) {
  const writes = useRef<Array<{ v: string; at: number }>>([])
  return useRef({
    note: (v: string) => {
      const now = Date.now()
      writes.current = [...writes.current.filter((w) => now - w.at < ttlMs), { v, at: now }]
    },
    has: (v: string) => {
      const now = Date.now()
      return writes.current.some((w) => w.v === v && now - w.at < ttlMs)
    },
  }).current
}
