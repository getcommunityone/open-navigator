import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { SetURLSearchParams } from 'react-router-dom'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { storyScreenIndex } from '../../utils/dataStory'
import { actsMode, useActs, type ActsApi, type ActsMode, type Hold } from './useActs'
import { useRecentWrites } from './useRecentWrites'
import { useScreenKeys } from './useScreenKeys'

interface Options {
  /** The screens in the story, in order (only their ids are read). */
  screens: ReadonlyArray<{ id: string }>
  /** The `?screen=` value in the URL. */
  screenParam: string
  setSp: SetURLSearchParams
  /** Changes when the place changes: the page lands on its screen again. */
  scopeKey: string
  /** Changes when the story itself changes (another story id): measurements and observers start again. */
  resetKey: unknown
  /** A dialog owns the keyboard and the scroll (the place picker). */
  dialogOpen: boolean
  reduced: boolean
  /** The reader moved to another screen (the Data Center Story plays its page-turn sound here). */
  onMove?: () => void
}

export interface StoryScreensApi {
  rootRef: React.RefObject<HTMLDivElement>
  /** The cover's Start button: while it is in view `onCover` is true. */
  startRef: React.RefObject<HTMLButtonElement>
  wide: boolean
  mode: ActsMode
  active: number
  activeRef: React.MutableRefObject<number>
  onCover: boolean
  goTo: (round: number) => void
  next: () => void
  prev: () => void
  acts: ActsApi
}

/**
 * The screen machine of a data story (#1224), shared by the Data Center Story and the topic stories: one screen at a time
 * (`useActs`: pinned on a wide screen, snapped on a phone), the screen in view written to `?screen=` and a `?screen=` link
 * landing on its screen, the cover (`[data-cover]`) and whether it is in view, keyboard paging (`useScreenKeys`), and focus
 * on the settled screen's heading after a keyboard move (#1146). Moved out of DataStory.tsx unchanged.
 */
export function useStoryScreens(opts: Options): StoryScreensApi {
  const { screens, screenParam, setSp, scopeKey, resetKey, dialogOpen, reduced } = opts
  const n = screens.length
  const onMoveRef = useRef(opts.onMove)
  onMoveRef.current = opts.onMove

  const wide = useMediaQuery('(min-width: 768px)')
  const mode = reduced ? 'snap' : actsMode(false, wide)
  const rootRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  // The cover in view (#1192): its Start button is the way forward, so neither the floating Next nor the phone bar's Next
  // shows beside it (the phone bar's Next would also skip the Overview, moving on from screen 0 before it is seen).
  const [onCover, setOnCover] = useState(true)
  const startRef = useRef<HTMLButtonElement>(null)
  const shownIds = useRef<string[]>([])
  useEffect(() => {
    // The cover's Start button when it has one (the Data Center Story), else the cover itself (the topic stories, whose one
    // Next is fixed at the bottom right, #1224).
    const el = startRef.current ?? rootRef.current?.querySelector<HTMLElement>('[data-cover]')
    if (!el || typeof IntersectionObserver === 'undefined') return
    // What sits under the sticky site header and the story's own bar does not count as visible.
    const header = document.querySelector<HTMLElement>('.site-header')
    const top = rootRef.current?.querySelector<HTMLElement>('.stance-top')
    const off = (header?.offsetHeight ?? 0) + (top?.offsetHeight ?? 0)
    const io = new IntersectionObserver(
      (entries) => {
        const e = entries[entries.length - 1]
        if (e) setOnCover(e.isIntersecting)
      },
      { threshold: 0.5, rootMargin: `-${off}px 0px 0px 0px` },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [resetKey, wide])

  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return
    const measure = () => {
      const header = document.querySelector<HTMLElement>('.site-header')
      const top = root.querySelector<HTMLElement>('.stance-top')
      root.style.setProperty('--hdr', `${header?.offsetHeight ?? 0}px`)
      root.style.setProperty('--top-h', `${top?.offsetHeight ?? 96}px`)
    }
    measure()
    const top = root.querySelector('.stance-top')
    const ro = typeof ResizeObserver !== 'undefined' && top ? new ResizeObserver(measure) : null
    if (top) ro?.observe(top)
    window.addEventListener('resize', measure)
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [resetKey])

  const activeRef = useRef(0)
  const ready = useRef(false)
  const lastWritten = useRef<string | null>(null)
  const recent = useRecentWrites()
  const dialogOpenRef = useRef(false)
  const viaKeyboard = useRef(false)
  useEffect(() => {
    const k = () => (viaKeyboard.current = true)
    const m = () => (viaKeyboard.current = false)
    window.addEventListener('keydown', k)
    window.addEventListener('pointerdown', m)
    window.addEventListener('wheel', m, { passive: true })
    return () => {
      window.removeEventListener('keydown', k)
      window.removeEventListener('pointerdown', m)
      window.removeEventListener('wheel', m)
    }
  }, [])

  const idAt = useCallback((i: number) => screens[i]?.id ?? '', [screens])
  // The story's own path. As the story unmounts, the scroller's last updates still arrive; writing `?screen=` then would
  // navigate relative to the story's route and pull the reader back into it, on its last screen (#997).
  const storyPath = useRef(window.location.pathname)
  /** True from landing until the reader moves (or 4s): the page is being kept on its screen while its content settles. */
  const settling = useRef(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    storyPath.current = window.location.pathname
    return () => {
      alive.current = false
    }
  }, [resetKey])
  const onActive = useCallback(
    (i: number) => {
      if (!alive.current || window.location.pathname !== storyPath.current || settling.current) return
      if (!ready.current || (i === activeRef.current && lastWritten.current != null)) return
      const moved = i !== activeRef.current
      activeRef.current = i
      setActive(i)
      lastWritten.current = idAt(i)
      recent.note(idAt(i))
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('screen', idAt(i))
          return next
        },
        { replace: true },
      )
      if (moved) onMoveRef.current?.()
    },
    [setSp, idAt, recent],
  )
  /** After a keyboard move, focus lands on the settled screen's heading (#1146): a screen reader reads where it is, Tab goes on
   *  to the screen's controls (Back, then Next), and the arrow keys still page because a heading isn't a control. */
  const onSettled = useCallback((h: Hold) => {
    if (dialogOpenRef.current) return
    // Resting on the opening (#1182): its Start and Next story buttons stay the first Tab stops; no screen takes focus.
    if (h.kind === 'cover') return
    const ae = document.activeElement as HTMLElement | null
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.closest('.stance-place'))) return
    const panel = rootRef.current?.querySelector<HTMLElement>(`[data-panel="${h.round}"]`)
    if (viaKeyboard.current) {
      const heading = panel?.querySelector<HTMLElement>('h2, h1, [role="heading"]')
      if (heading && !heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1')
      const target = heading ?? panel?.querySelector<HTMLElement>('.stance-next') ?? panel?.querySelector<HTMLElement>('.stance-answers button:not(:disabled)')
      target?.focus({ preventScroll: true })
    } else if (panel && (ae == null || ae === document.body || !panel.contains(ae))) {
      // After wheel or pointer scrolling nothing visibly takes focus, but the screen becomes the starting point for Tab, so
      // the next Tab stop is its first control.
      panel.focus({ preventScroll: true })
    }
  }, [])

  const acts = useActs({
    mode,
    smooth: !reduced,
    gameRef: rootRef,
    // The last screen is the untimed end panel, like the challenge's end screen.
    count: Math.max(0, n - 1),
    isAnswered: () => false,
    onActive,
    onSettled,
  })

  // Land on the screen named in the URL once the screens exist, then start following the scroll.
  useEffect(() => {
    if (n === 0) return
    ready.current = false
    // The story opens on its first screen's hold (overview), not on the empty start of its timeline.
    // When the screens change (a new place, or empty screens dropping out as data arrives), the reader stays on the
    // screen they were on, found by its id.
    const fromUrl = storyScreenIndex(screens, screenParam)
    const wasOn = shownIds.current[activeRef.current]
    shownIds.current = screens.map((x) => x.id)
    const stay = wasOn ? screens.findIndex((x) => x.id === wasOn) : -1
    const at = Math.max(0, fromUrl >= 0 ? fromUrl : stay)
    // The opening (#1182) is a cover hold at the top: a fresh visit with no ?screen opens on it, and a reader still above
    // the first screen stays on it when the screens rebuild; a reader on screen 0 (or a ?screen link) lands on its hold.
    const coverFirst = fromUrl < 0 && at === 0
    const land = (behavior: ScrollBehavior) => {
      const h = acts.holds().find((x) => x.round === at && (x.kind === 'q' || x.kind === 'end'))
      const keepCover = coverFirst && (h == null || window.scrollY < h.pos - 2)
      // The page can arrive scrolled (a previous page's offset, e.g. home's Data stories section), so the story always
      // moves to its screen; before #991 it stayed put at screen 0 and opened mid-way, on a screen that wasn't the active one.
      const target = keepCover ? 0 : at > 0 || mode === 'pinned' ? h?.pos : (h?.pos ?? 0)
      if (target != null && Math.abs(target - window.scrollY) > 2) window.scrollTo({ top: target, behavior })
    }
    land('auto')
    activeRef.current = at
    setActive(at)
    lastWritten.current = screens[at]?.id ?? null
    const id = requestAnimationFrame(() => requestAnimationFrame(() => (ready.current = true)))
    // The page is put on its screen before everything has its final height: the top bar (which sets every screen's height)
    // and the data for the place, which arrives after a change of place. While the reader has not moved, the page is kept on
    // the screen it landed on and the scroller's reports are ignored; otherwise the shifting page reads as another screen,
    // often a later one (#999). Pinned positions follow a ScrollTrigger refresh, so the page lands again once they settle.
    settling.current = true
    let again = 0
    const reland = () => {
      window.clearTimeout(again)
      again = window.setTimeout(() => land('instant' as ScrollBehavior), 300)
    }
    const top = rootRef.current?.querySelector('.stance-top')
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(reland) : null
    if (top) ro?.observe(top)
    if (rootRef.current) ro?.observe(rootRef.current)
    const stop = () => {
      ro?.disconnect()
      window.clearTimeout(again)
      settling.current = false
    }
    const moves = ['pointerdown', 'wheel', 'keydown', 'touchstart'] as const
    moves.forEach((e) => window.addEventListener(e, stop, { once: true, passive: true }))
    const timer = window.setTimeout(stop, 4000)
    return () => {
      cancelAnimationFrame(id)
      window.clearTimeout(timer)
      moves.forEach((e) => window.removeEventListener(e, stop))
      stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n, mode, scopeKey, screens])

  // A screen in the URL that changed from outside (a link, the back button) moves the page.
  useEffect(() => {
    if (!ready.current || !screenParam || lastWritten.current === screenParam || recent.has(screenParam)) return
    const at = storyScreenIndex(screens, screenParam)
    if (at >= 0 && at !== activeRef.current) acts.goToRound(at)
  }, [screenParam, screens, acts, recent])

  const goTo = acts.goToRound
  useEffect(() => acts.lock(dialogOpen), [dialogOpen, acts])
  dialogOpenRef.current = dialogOpen

  const next = useCallback(() => goTo(Math.min(activeRef.current + 1, n - 1)), [goTo, n])
  const prev = useCallback(() => goTo(Math.max(activeRef.current - 1, 0)), [goTo])
  useScreenKeys({
    next,
    prev,
    first: () => goTo(0),
    last: () => goTo(n - 1),
    enabled: !dialogOpen,
  })

  return { rootRef, startRef, wide, mode, active, activeRef, onCover, goTo, next, prev, acts }
}
