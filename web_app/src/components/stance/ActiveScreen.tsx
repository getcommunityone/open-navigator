import { createContext, memo, useContext, useSyncExternalStore, type ReactNode } from 'react'

/**
 * The screen the reader is on (#1411). Moving to the next screen used to re-render every panel of the story (all of them are
 * mounted at once), because `active` was a prop of each. The index now lives in a small store: a panel subscribes to the one
 * question it asks ("am I the active screen?"), so a Next re-renders the two frames whose answer changed, and the rest of each
 * panel, held by `MemoPanel`, is left alone.
 */
export interface ActiveScreenStore {
  get: () => number | null
  set: (i: number) => void
  subscribe: (fn: () => void) => () => void
}

export function createActiveScreenStore(): ActiveScreenStore {
  let at: number | null = null
  const subs = new Set<() => void>()
  return {
    get: () => at,
    set: (i) => {
      if (i === at) return
      at = i
      subs.forEach((fn) => fn())
    },
    subscribe: (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    },
  }
}

export const ActiveScreenContext = createContext<ActiveScreenStore | null>(null)

/** Whether screen `index` is the one in view. Without a provider (a story that still passes `active`), `fallback` decides. */
export function useScreenActive(index: number, fallback = false): boolean {
  const store = useContext(ActiveScreenContext)
  return useSyncExternalStore(
    store ? store.subscribe : noSubscribe,
    () => (store ? store.get() === index : fallback),
    () => (store ? store.get() === index : fallback),
  )
}
const noSubscribe = () => () => {}

interface MemoPanelProps {
  /** Everything `render` reads other than the active screen; the panel is drawn again only when one of them changes. */
  deps: readonly unknown[]
  render: () => ReactNode
}

/** One screen's content, drawn again only when its `deps` change (never because the reader moved to another screen). */
export const MemoPanel = memo(
  function MemoPanel({ render }: MemoPanelProps) {
    return <>{render()}</>
  },
  (a, b) => a.deps.length === b.deps.length && a.deps.every((d, i) => Object.is(d, b.deps[i])),
)
