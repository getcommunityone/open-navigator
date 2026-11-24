import { useCallback, useEffect, useMemo, useRef, type RefObject } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'

/** Pinned scroll distance per screen, as a share of the frame height (the brief: roughly 220 to 320 %). */
const DIST = 2.8
/** Where the beats sit on a round's 0..1 timeline. */
export const QUESTION_HOLD = 0.62
export const REVEAL_HOLD = 0.9

export type HoldKind = 'q' | 'r' | 'cover'
export interface Hold {
  pos: number
  /** 0-based screen, or `count` for the untimed end screen. */
  round: number
  kind: HoldKind | 'end'
}

/**
 * How the screens move (#915).
 * `pinned`: a wide screen with motion allowed. Every screen is pinned and scrubbed by the scroll (GSAP ScrollTrigger + Lenis).
 * `snap`: a phone with motion allowed. Full-height screens, native scrolling with CSS scroll snap (one screen per swipe), and
 * each screen's content animates in as it arrives and out as it leaves.
 * `stacked`: reduced motion. Plain panels, native scrolling, nothing moves.
 */
export type ActsMode = 'pinned' | 'snap' | 'stacked'

/** Which mode a page gets. Reduced motion always wins. */
export function actsMode(reducedMotion: boolean, wide: boolean): ActsMode {
  if (reducedMotion) return 'stacked'
  return wide ? 'pinned' : 'snap'
}

/** The class on `<html>` that turns scroll snap on for the page (see stance.css). Removed when the page unmounts. */
const SNAP_CLASS = 'stance-snap'

/**
 * Marks each screen with where it is: `data-state="in"` when it fills the frame, `above` or `below` otherwise, and
 * `data-leaving` once it has started to go. stance.css moves the content between those states, so a screen's title and blocks
 * rise in when it arrives, fade as it leaves, and play again on every return.
 */
function paintStates(game: HTMLElement, screens: HTMLElement[]): void {
  const off = frameOffset(game)
  const vh = window.innerHeight
  for (const el of screens) {
    const r = el.getBoundingClientRect()
    const frame = Math.max(1, Math.min(r.height, vh - off))
    const vis = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, off)) / frame
    const state = vis >= 0.6 ? 'in' : r.top < off ? 'above' : 'below'
    if (el.dataset.state !== state) el.dataset.state = state
    // "Leaving" is a screen that is going, not one that is still arriving: it depends on which way its share of the frame moves.
    const prev = lastVis.get(el) ?? vis
    lastVis.set(el, vis)
    const leaving = vis > prev + 0.001 ? false : vis < prev - 0.001 ? vis < 0.93 : el.hasAttribute('data-leaving')
    el.toggleAttribute('data-leaving', state === 'in' && leaving)
  }
}
const lastVis = new WeakMap<HTMLElement, number>()

function clearStates(screens: HTMLElement[]): void {
  for (const el of screens) {
    el.removeAttribute('data-state')
    el.removeAttribute('data-leaving')
  }
}

interface Options {
  mode: ActsMode
  gameRef: RefObject<HTMLElement>
  /** Number of timed screens (game rounds, or story screens). */
  count: number
  /**
   * True (default, the challenge): one more, untimed panel follows the timed ones (the end screen).
   * False: every panel is timed. Panels are the elements with a `data-panel` attribute, in order.
   */
  endPanel?: boolean
  /** Whether round i has a confirmed answer: only answered rounds get a reveal hold. */
  isAnswered: (round: number) => boolean
  onActive: (round: number) => void
  /** The scroll settled on a hold. */
  onSettled: (hold: Hold) => void
  /** Smooth scrolling is allowed (not reduced motion). */
  smooth: boolean
  /**
   * The challenge's beats (#899): the chart draw, the question and the reveal are played by the round itself on a clock, not
   * scrubbed by the scroll, so the timeline leaves --draw, --reveal and the question block alone.
   */
  beats?: boolean
}

export interface ActsApi {
  holds: () => Hold[]
  goToRound: (round: number, duration?: number) => void
  goToReveal: (round: number) => void
  /** Freeze or release scrolling (a popover is open). */
  lock: (locked: boolean) => void
}

const clamp = (n: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, n))

/** Distance from the top of the window to the bottom of the site header and the sticky HUD bar. */
function frameOffset(game: HTMLElement): number {
  const header = document.querySelector<HTMLElement>('.site-header')
  const top = game.querySelector<HTMLElement>('.stance-top')
  return (header?.offsetHeight ?? 0) + (top?.offsetHeight ?? 0)
}

/**
 * The shared scrolling engine of the Data Center Challenge (rounds) and the Data Center Story (screens): a screen is any
 * element with `data-panel`, using the `.stance-card`, `.stance-word`, `.stance-head`, `.stance-right`, `.stance-grid`,
 * `.stance-qblock`, `.stance-reveal` and `.stance-nav` hooks that the timeline animates. Only the challenge has reveal holds
 * (`isAnswered`) and a cover; a story passes `endPanel: false` or `isAnswered: () => false` and gets one hold per screen.
 *
 * The game's scrolling. Pinned mode (the kinetic reference's technique): Lenis for inertial scrolling, driven from the
 * gsap ticker; every round is an act pinned for about 280 % of the frame while a timeline scrubs through its beats
 * (category card and round word, chart build, title words, question hold, reveal, exit); the scroll glides to the hold points
 * and one gesture never passes the next one.
 * Snap mode (phones): full-height screens and the browser's own scroll snap, so touch momentum and the address bar are the
 * browser's business; the screen in view is marked and stance.css plays its entrance and exit.
 * Stacked mode (reduced motion): plain panels, native scrolling, IntersectionObserver for the round in view.
 * Everything created here is torn down on unmount, so no other page is affected.
 */
export function useActs(opts: Options): ActsApi {
  const o = useRef(opts)
  o.current = opts
  const api = useRef<ActsApi>({ holds: () => [], goToRound: () => {}, goToReveal: () => {}, lock: () => {} })

  const { mode, count, gameRef } = opts
  useEffect(() => {
    const game = gameRef.current
    if (!game || count === 0) return
    const acts = Array.from(game.querySelectorAll<HTMLElement>('[data-panel]'))
    const withEnd = o.current.endPanel !== false
    if (acts.length !== count + (withEnd ? 1 : 0)) return
    const last = acts.length - 1
    const endEl = withEnd ? acts[count]! : null

    const cover = game.querySelector<HTMLElement>('[data-cover]')

    if (mode !== 'pinned') {
      const snap = mode === 'snap'
      const screens = snap ? [...(cover ? [cover] : []), ...acts] : []
      const root = document.documentElement
      if (snap) root.classList.add(SNAP_CLASS)
      const holds = (): Hold[] => {
        const off = frameOffset(game)
        return acts.map((el, i) => ({
          pos: Math.max(0, el.getBoundingClientRect().top + window.scrollY - off),
          round: i,
          kind: withEnd && i === count ? 'end' : 'q',
        }))
      }
      // A move the page itself makes (Next, a key, a link) may cross several screens; a swipe may not (see `fence`).
      let programmatic = false
      const go = (round: number) => {
        const h = holds()[Math.min(Math.max(round, 0), last)]
        if (!h) return
        if (Math.abs(h.pos - window.scrollY) > 2) programmatic = true
        window.scrollTo({ top: h.pos, behavior: o.current.smooth ? 'smooth' : 'auto' })
      }
      api.current = { holds, goToRound: go, goToReveal: () => {}, lock: () => {} }
      /** Where each screen rests (the cover included), top to bottom. */
      const stops = (): number[] => {
        const off = frameOffset(game)
        return screens.map((el) => Math.max(0, Math.round(el.getBoundingClientRect().top + window.scrollY - off)))
      }
      // The screen the reader was resting on when the gesture began. Scroll snap stops a swipe at the next screen; this is the
      // backstop for a hard fling that carries past it: the page is put on that next screen and the fling ends there.
      let anchor: number | null = null
      const fence = () => {
        if (programmatic || anchor == null) return
        const ps = stops()
        const y = window.scrollY
        let i = 0
        ps.forEach((p, k) => {
          if (Math.abs(p - anchor!) < Math.abs(ps[i]! - anchor!)) i = k
        })
        // Past the last screen (what follows the page) and above the first, the page scrolls freely.
        const hi = i < ps.length - 1 ? ps[i + 1]! : Infinity
        const lo = i > 0 ? ps[i - 1]! : -Infinity
        if (y > hi + 1) window.scrollTo({ top: hi, behavior: 'instant' as ScrollBehavior })
        else if (y < lo - 1) window.scrollTo({ top: lo, behavior: 'instant' as ScrollBehavior })
      }
      let settleTimer = 0
      const settle = () => {
        const pos = window.scrollY
        programmatic = false
        const rest = stops().find((p) => Math.abs(p - pos) <= 8)
        if (rest != null) anchor = rest
        const h = holds().find((x) => Math.abs(x.pos - pos) <= 8)
        if (h) o.current.onSettled(h)
      }
      const check = () => {
        const off = frameOffset(game)
        const line = off + window.innerHeight * 0.35
        let idx = 0
        acts.forEach((el, i) => {
          if (el.getBoundingClientRect().top <= line) idx = i
        })
        o.current.onActive(idx)
        if (snap) {
          fence()
          paintStates(game, screens)
          window.clearTimeout(settleTimer)
          settleTimer = window.setTimeout(settle, 140)
        }
      }
      // A mouse wheel or trackpad on a narrow window: scroll snap alone lets one hard flick pass several screens, so a wheel
      // gesture is turned into exactly one screen. A block that can still scroll that way keeps the wheel, and so does the
      // page beyond the first and last screens.
      let wheelLast = 0
      let wheelArmed = true
      let wheelAt = 0
      const onWheel = (e: WheelEvent) => {
        if (e.ctrlKey || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return
        const now = performance.now()
        const quiet = now - wheelLast > 150
        wheelLast = now
        for (let el = e.target as HTMLElement | null; el && el !== game && el !== document.body; el = el.parentElement) {
          if (el.scrollHeight <= el.clientHeight + 1) continue
          const oy = getComputedStyle(el).overflowY
          if (oy !== 'auto' && oy !== 'scroll') continue
          if (e.deltaY > 0 ? el.scrollTop + el.clientHeight < el.scrollHeight - 1 : el.scrollTop > 0) return
        }
        const y = window.scrollY
        const hs = holds()
        const next = e.deltaY > 0 ? hs.find((h) => h.pos > y + 4) : [...hs].reverse().find((h) => h.pos < y - 4)
        if (!next) return
        e.preventDefault()
        if (quiet || now - wheelAt > 1500) wheelArmed = true
        if (!wheelArmed) return
        wheelArmed = false
        wheelAt = now
        programmatic = true
        window.scrollTo({ top: next.pos, behavior: o.current.smooth ? 'smooth' : 'auto' })
      }
      if (snap) window.addEventListener('wheel', onWheel, { passive: false })
      const io = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(check, { threshold: [0, 0.25, 0.5, 0.75, 1] }) : null
      acts.forEach((a) => io?.observe(a))
      window.addEventListener('scroll', check, { passive: true })
      window.addEventListener('resize', check)
      check()
      return () => {
        io?.disconnect()
        window.clearTimeout(settleTimer)
        window.removeEventListener('scroll', check)
        window.removeEventListener('resize', check)
        window.removeEventListener('wheel', onWheel)
        root.classList.remove(SNAP_CLASS)
        clearStates(screens)
        api.current = { holds: () => [], goToRound: () => {}, goToReveal: () => {}, lock: () => {} }
      }
    }

    gsap.registerPlugin(ScrollTrigger)
    ScrollTrigger.config({ ignoreMobileResize: true })
    const lenis = new Lenis({ lerp: 0.11, smoothWheel: true, syncTouch: false })
    // Until the player first touches the page, nothing snaps: the opening round plays its own arrival instead.
    let interacted = false
    const mark = () => {
      interacted = true
    }
    window.addEventListener('wheel', mark, { passive: true })
    window.addEventListener('touchstart', mark, { passive: true })
    window.addEventListener('keydown', mark)
    // The hold the reader last rested on. One gesture never carries past the hold next to it (see `limit`).
    let anchor: number | null = null
    // A move the page itself is making (Continue, a rail stop, a key): it may cross several screens.
    let programmatic = false
    let progTimer = 0
    const settleAt = () => {
      const pos = window.scrollY
      const h = holds().find((x) => Math.abs(x.pos - pos) <= 8)
      if (h) {
        anchor = h.pos
        o.current.onSettled(h)
      }
    }
    lenis.on('scroll', ScrollTrigger.update)
    // Snapping to the holds is done through Lenis (not ScrollTrigger's own snap tween, which fights Lenis's smoothing):
    // when scrolling has been still for 160 ms, glide to the hold in the direction the player was travelling.
    let snapTimer = 0
    let lastPos = window.scrollY
    let lastDir = 1
    const power2InOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2)
    const maybeSnap = () => {
      if (!interacted || lenis.isStopped) return
      if (lenis.isScrolling) {
        snapTimer = window.setTimeout(maybeSnap, 80)
        return
      }
      const pos = window.scrollY
      const ps = holds()
        .map((h) => h.pos)
        .sort((a, b) => a - b)
      if (!ps.length) return
      const pick =
        lastDir >= 0 ? (ps.find((p) => p >= pos - 6) ?? ps[ps.length - 1]!) : ([...ps].reverse().find((p) => p <= pos + 6) ?? ps[0]!)
      if (Math.abs(pick - pos) <= 1) {
        settleAt()
        return
      }
      const dist = Math.abs(pick - pos)
      lenis.scrollTo(pick, {
        duration: Math.min(0.62, Math.max(0.34, dist / 4000)),
        easing: power2InOut,
        onComplete: settleAt,
      })
    }
    // A hard flick of the wheel or trackpad stops at the next screen instead of flying past several: once the scroll is headed
    // beyond the hold next to the one the reader was on, it is taken there and held until it arrives.
    const limit = () => {
      const ps = holds()
        .map((h) => h.pos)
        .sort((a, b) => a - b)
      if (ps.length < 2) return
      const from = anchor ?? window.scrollY
      let i = 0
      ps.forEach((p, k) => {
        if (Math.abs(p - from) < Math.abs(ps[i]! - from)) i = k
      })
      // Past the last hold (the end screen and what follows it) the page scrolls freely.
      const hi = i < ps.length - 1 ? ps[i + 1]! : Infinity
      const lo = i > 0 ? ps[i - 1]! : -Infinity
      const target = lenis.targetScroll
      const bound = target > hi + 2 ? hi : target < lo - 2 ? lo : null
      if (bound == null) return
      programmatic = true
      window.clearTimeout(snapTimer)
      window.clearTimeout(progTimer)
      const done = () => {
        window.clearTimeout(progTimer)
        programmatic = false
        settleAt()
      }
      lenis.scrollTo(bound, { duration: 0.55, easing: power2InOut, lock: true, onComplete: done })
      progTimer = window.setTimeout(done, 900)
    }
    lenis.on('scroll', () => {
      const pos = window.scrollY
      if (Math.abs(pos - lastPos) > 0.5) lastDir = pos > lastPos ? 1 : -1
      lastPos = pos
      if (programmatic) return
      window.clearTimeout(snapTimer)
      snapTimer = window.setTimeout(maybeSnap, 160)
      if (interacted) limit()
    })
    const tick = (time: number) => lenis.raf(time * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)

    const triggers: Array<ScrollTrigger | undefined> = []
    const hasCover = Boolean(cover)
    // The screens the timeline does not pin (the cover and the end screen) get their entrance and exit from their state.
    const loose = [cover, withEnd ? acts[count]! : null].filter((e): e is HTMLElement => e != null)
    const holds = (): Hold[] => {
      const out: Hold[] = hasCover ? [{ pos: 0, round: 0, kind: 'cover' }] : []
      for (let i = 0; i < count; i++) {
        const st = triggers[i]
        if (!st) continue
        const span = st.end - st.start
        out.push({ pos: Math.round(st.start + QUESTION_HOLD * span), round: i, kind: 'q' })
        if (o.current.isAnswered(i)) out.push({ pos: Math.round(st.start + REVEAL_HOLD * span), round: i, kind: 'r' })
      }
      if (endEl) out.push({ pos: Math.max(0, Math.round(endEl.getBoundingClientRect().top + window.scrollY - frameOffset(game))), round: count, kind: 'end' })
      return out
    }
    const scrollToPos = (pos: number, duration = 0.9) => {
      interacted = true
      programmatic = true
      window.clearTimeout(progTimer)
      const done = () => {
        window.clearTimeout(progTimer)
        programmatic = false
        settleAt()
      }
      lenis.scrollTo(pos, { duration, onComplete: done })
      progTimer = window.setTimeout(done, duration * 1000 + 400)
    }
    api.current = {
      holds,
      goToRound: (r, d) => {
        const h = holds().find((x) => x.round === Math.min(Math.max(r, 0), last) && (x.kind === 'q' || x.kind === 'end'))
        if (h) scrollToPos(h.pos, d)
      },
      goToReveal: (r) => {
        const h = holds().find((x) => x.round === r && x.kind === 'r')
        if (h) scrollToPos(h.pos)
      },
      lock: (locked) => (locked ? lenis.stop() : lenis.start()),
    }

    const syncs: Array<() => void> = []
    const ctx = gsap.context(() => {
      acts.slice(0, count).forEach((act, i) => {
        const q = <T extends Element = HTMLElement>(sel: string) => act.querySelector<T>(sel)
        const card = q('.stance-card')
        const word = q('.stance-word')
        const right = q('.stance-right')
        const qblock = Array.from(act.querySelectorAll('.stance-qblock, .stance-reveal, .stance-nav'))
        const grid = q('.stance-grid')
        const head = q('.stance-head')
        const draw = { v: 0 }
        const reveal = { v: 0 }
        // The headline's words rise out of their masks with the scroll (stance.css reads --title per word).
        const title = { v: 0 }
        act.style.setProperty('--title', '0')
        // The three values are written from the timeline as a whole, not from each tween: a timeline that starts part-way
        // through (a deep link, a restored scroll position) renders without firing its tweens' own callbacks.
        const sync = () => {
          act.style.setProperty('--title', title.v.toFixed(3))
          if (o.current.beats) return
          act.style.setProperty('--draw', draw.v.toFixed(3))
          act.style.setProperty('--reveal', reveal.v.toFixed(3))
        }
        syncs.push(sync)
        const beats = Boolean(o.current.beats)
        if (!beats) {
          act.style.setProperty('--draw', '0')
          act.style.setProperty('--reveal', '0')
        }
        const tl = gsap.timeline({
          defaults: { ease: 'none' },
          onUpdate: sync,
          scrollTrigger: {
            onRefresh: sync,
            trigger: act,
            start: () => `top top+=${frameOffset(game)}`,
            end: () => `+=${Math.round(act.offsetHeight * DIST)}`,
            pin: true,
            scrub: 0.3,
            anticipatePin: 1,
            invalidateOnRefresh: true,
          },
        })
        // (a) the category card and the round word arrive; the word drifts at its own, slower pace and cross-fades
        if (card) tl.fromTo(card, { x: -90, opacity: 0 }, { x: 0, opacity: 1, duration: 0.16, ease: 'expo.out' }, 0)
        if (word) {
          tl.fromTo(word, { opacity: 0 }, { opacity: 1, duration: 0.18 }, 0)
          tl.fromTo(word, { yPercent: 30, scale: 0.92 }, { yPercent: -14, scale: 1, duration: 1 }, 0)
          tl.to(word, { opacity: 0, duration: 0.06 }, 0.94)
        }
        // (b) the chart builds with the scroll
        if (right) tl.fromTo(right, { opacity: 0, y: 48 }, { opacity: 1, y: 0, duration: 0.14, ease: 'expo.out' }, 0.1)
        if (!beats) tl.to(draw, { v: 1, duration: 0.34 }, 0.16)
        // (c) the headline, then the statement, resolve to a sharp hold
        if (head) tl.fromTo(head, { opacity: 0, y: 44 }, { opacity: 1, y: 0, duration: 0.2, ease: 'expo.out' }, 0.22)
        tl.to(title, { v: 1, duration: 0.24, ease: 'power2.out' }, 0.22)
        // the statement resolves to a sharp hold with the answers
        if (qblock.length && !beats) tl.fromTo(qblock, { opacity: 0, y: 36, filter: 'blur(10px)' }, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.2, ease: 'expo.out' }, 0.36)
        // (d) the reveal bars extend
        if (!beats) tl.to(reveal, { v: 1, duration: 0.18 }, 0.7)
        // (e) exit
        if (grid) tl.to(grid, { opacity: 0.3, y: -28, duration: 0.07 }, 0.93)
        triggers[i] = tl.scrollTrigger as ScrollTrigger
      })

      const rail = game
      const master = ScrollTrigger.create({
        start: 0,
        end: 'max',
        onUpdate: (self) => {
          const max = ScrollTrigger.maxScroll(window)
          rail.style.setProperty('--progress', max > 0 ? clamp(self.scroll() / max).toFixed(4) : '0')
          const pos = self.scroll()
          let best = 0
          let bestD = Infinity
          for (const h of holds()) {
            if (h.kind === 'r' || h.kind === 'cover') continue
            const d = Math.abs(h.pos - pos)
            if (d < bestD) {
              bestD = d
              best = h.round
            }
          }
          o.current.onActive(best)
          paintStates(game, loose)
        },
      })
      triggers.push(master)
    }, game)

    ScrollTrigger.refresh()
    syncs.forEach((f) => f())
    paintStates(game, loose)
    const onResize = () => ScrollTrigger.refresh()
    const tb = game.querySelector('.stance-top')
    const ro = typeof ResizeObserver !== 'undefined' && tb ? new ResizeObserver(() => ScrollTrigger.refresh()) : null
    if (tb) ro?.observe(tb)
    window.addEventListener('orientationchange', onResize)

    return () => {
      window.clearTimeout(snapTimer)
      window.clearTimeout(progTimer)
      clearStates(loose)
      window.removeEventListener('wheel', mark)
      window.removeEventListener('touchstart', mark)
      window.removeEventListener('keydown', mark)
      window.removeEventListener('orientationchange', onResize)
      ro?.disconnect()
      ctx.revert()
      triggers.forEach((t) => t?.kill())
      acts.forEach((a) => {
        a.style.removeProperty('--draw')
        a.style.removeProperty('--reveal')
        a.style.removeProperty('--title')
      })
      gsap.ticker.remove(tick)
      gsap.ticker.lagSmoothing(500, 33)
      lenis.destroy()
      api.current = { holds: () => [], goToRound: () => {}, goToReveal: () => {}, lock: () => {} }
    }
  }, [mode, count, gameRef, opts.endPanel])

  const holds = useCallback(() => api.current.holds(), [])
  const goToRound = useCallback((r: number, d?: number) => api.current.goToRound(r, d), [])
  const goToReveal = useCallback((r: number) => api.current.goToReveal(r), [])
  const lock = useCallback((l: boolean) => api.current.lock(l), [])
  return useMemo(() => ({ holds, goToRound, goToReveal, lock }), [holds, goToRound, goToReveal, lock])
}
