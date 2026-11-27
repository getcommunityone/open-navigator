import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { SetURLSearchParams } from 'react-router-dom'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { storyScreenIndex } from '../../utils/dataStory'
import { actsMode, useActs, type ActsApi, type ActsMode, type Hold } from './useActs'
import { useRecentWrites } from './useRecentWrites'
import { useScreenKeys } from './useScreenKeys'
import { useSwipeNav } from '../../hooks/useSwipeNav'

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
  wide: boolean
  mode: ActsMode
  active: number
  activeRef: React.MutableRefObject<number>
  goTo: (round: number) => void
  next: () => void
  prev: () => void
  acts: ActsApi
}

/**
 * The screen machine of a data story (#1224), shared by the Data Center Story and the topic stories: one screen at a time
 * (`useActs`: pinned on a wide screen, snapped on a phone), the screen in view written to `?screen=` and a `?screen=` link
 * landing on its screen, keyboard paging (`useScreenKeys`), and focus
 * on the settled screen's heading after a keyboard move (#1146), re-aiming a jump the growing page threw off (#1208) and the
 * sideways swipe (#1222). Moved out of DataStory.tsx unchanged.
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
  const shownIds = useRef<string[]>([])

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
  /** The screen the reader last asked for (a segment, Next, Back, a key, a swipe), until the page settles on it (#1208). */
  const intent = useRef<{ id: string; tries: number } | null>(null)
  const screensRef = useRef(screens)
  screensRef.current = screens
  const goToRef = useRef<(i: number) => void>(() => {})
  const ready = useRef(false)
  const lastWritten = useRef<string | null>(null)
  const recent = useRecentWrites()
  const dialogOpenRef = useRef(false)
  const viaKeyboard = useRef(false)
  useEffect(() => {
    const k = () => (viaKeyboard.current = true)
    const m = () => {
      viaKeyboard.current = false
      // The reader moving by hand drops a pending jump (#1208); a button or swipe sets a new one after this.
      intent.current = null
    }
    window.addEventListener('keydown', k)
    window.addEventListener('pointerdown', m)
    window.addEventListener('wheel', m, { passive: true })
    window.addEventListener('touchstart', m, { passive: true })
    return () => {
      window.removeEventListener('keydown', k)
      window.removeEventListener('pointerdown', m)
      window.removeEventListener('wheel', m)
      window.removeEventListener('touchstart', m)
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
    // A jump made while the page was still growing (a progress segment pressed as the place's data arrived, #1208) can land
    // on another screen: the pixels it aimed for moved. Re-aim at the screen asked for, by id, a few times at most.
    const want = intent.current
    if (want) {
      const at = screensRef.current.findIndex((x) => x.id === want.id)
      if (at >= 0 && h.round !== at && want.tries < 3) {
        want.tries += 1
        goToRef.current(at)
        return
      }
      intent.current = null
    }
    if (dialogOpenRef.current) return
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
    // The screen the reader asked for wins over the URL and the old position when the screens rebuild under a jump (#1208).
    const fromIntent = intent.current ? screens.findIndex((x) => x.id === intent.current!.id) : -1
    const fromUrl = fromIntent >= 0 ? fromIntent : storyScreenIndex(screens, screenParam)
    const wasOn = shownIds.current[activeRef.current]
    shownIds.current = screens.map((x) => x.id)
    const stay = wasOn ? screens.findIndex((x) => x.id === wasOn) : -1
    const at = Math.max(0, fromUrl >= 0 ? fromUrl : stay)
    const land = (behavior: ScrollBehavior) => {
      const h = acts.holds().find((x) => x.round === at && (x.kind === 'q' || x.kind === 'end'))
      // The page can arrive scrolled (a previous page's offset, e.g. home's Data stories section), so the story always
      // moves to its screen; before #991 it stayed put at screen 0 and opened mid-way, on a screen that wasn't the active one.
      const target = at > 0 || mode === 'pinned' ? h?.pos : (h?.pos ?? 0)
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
    // 10s, not 4s (#1290): a title whose height changes when slower caption facts arrive must still re-land the page.
    const timer = window.setTimeout(stop, 10_000)
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

  goToRef.current = acts.goToRound
  /** Every move the reader makes goes through here, so the intended screen is known when the page settles (#1208). */
  const goTo = useCallback(
    (i: number) => {
      const at = Math.max(0, Math.min(i, screensRef.current.length - 1))
      const id = screensRef.current[at]?.id
      // A move to the screen already shown sets no pending jump (it may never settle again to clear it).
      intent.current = id && at !== activeRef.current ? { id, tries: 0 } : null
      acts.goToRound(i)
    },
    [acts],
  )
  // Swipe between screens on a touch screen (#1222): left = next (on the cover, Start), right = back.
  useSwipeNav({
    rootRef,
    enabled: !dialogOpen,
    onNext: () => {
      if (activeRef.current < n - 1) goTo(activeRef.current + 1)
    },
    onPrev: () => {
      if (activeRef.current > 0) goTo(activeRef.current - 1)
    },
  })
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

  return { rootRef, wide, mode, active, activeRef, goTo, next, prev, acts }
}
