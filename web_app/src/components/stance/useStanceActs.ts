import { useCallback, useEffect, useMemo, useRef, type RefObject } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'

/** Pinned scroll distance per round, as a share of the frame height (the brief: roughly 220 to 320 %). */
const DIST = 2.8
/** Where the beats sit on a round's 0..1 timeline. */
export const QUESTION_HOLD = 0.62
export const REVEAL_HOLD = 0.9

export type HoldKind = 'q' | 'r' | 'cover'
export interface Hold {
  pos: number
  /** 0-based round, or `count` for the end screen. */
  round: number
  kind: HoldKind | 'end'
}

interface Options {
  /** True: pinned, scrubbed acts with Lenis. False: plain stacked panels with native scrolling. */
  animated: boolean
  gameRef: RefObject<HTMLElement>
  /** Number of rounds (the end screen is one more act). */
  count: number
  /** Whether round i has a confirmed answer: only answered rounds get a reveal hold. */
  isAnswered: (round: number) => boolean
  onActive: (round: number) => void
  /** The scroll settled on a hold. */
  onSettled: (hold: Hold) => void
  /** Smooth scrolling is allowed (not reduced motion). */
  smooth: boolean
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
 * The game's scrolling. Animated mode (the kinetic reference's technique): Lenis for inertial scrolling, driven from the
 * gsap ticker; every round is an act pinned for about 280 % of the frame while a timeline scrubs through its beats
 * (category card and round word, chart build, question hold, reveal, exit); one ScrollTrigger snaps to the hold points.
 * Plain mode: stacked panels, native scrolling, IntersectionObserver for the round in view.
 * Everything created here is torn down on unmount, so no other page is affected.
 */
export function useStanceActs(opts: Options): ActsApi {
  const o = useRef(opts)
  o.current = opts
  const api = useRef<ActsApi>({ holds: () => [], goToRound: () => {}, goToReveal: () => {}, lock: () => {} })

  const { animated, count, gameRef } = opts
  useEffect(() => {
    const game = gameRef.current
    if (!game || count === 0) return
    const acts = Array.from(game.querySelectorAll<HTMLElement>('[data-panel]'))
    if (acts.length !== count + 1) return
    const endEl = acts[count]!

    if (!animated) {
      const holds = (): Hold[] => {
        const off = frameOffset(game)
        return acts.map((el, i) => ({
          pos: Math.max(0, el.getBoundingClientRect().top + window.scrollY - off),
          round: i,
          kind: i === count ? 'end' : 'q',
        }))
      }
      const go = (round: number) => {
        const h = holds()[Math.min(Math.max(round, 0), count)]
        if (h) window.scrollTo({ top: h.pos, behavior: o.current.smooth ? 'smooth' : 'auto' })
      }
      api.current = { holds, goToRound: go, goToReveal: () => {}, lock: () => {} }
      const check = () => {
        const off = frameOffset(game)
        const line = off + window.innerHeight * 0.35
        let idx = 0
        acts.forEach((el, i) => {
          if (el.getBoundingClientRect().top <= line) idx = i
        })
        o.current.onActive(idx)
      }
      const io = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(check, { threshold: [0, 0.25, 0.5, 0.75, 1] }) : null
      acts.forEach((a) => io?.observe(a))
      window.addEventListener('scroll', check, { passive: true })
      check()
      return () => {
        io?.disconnect()
        window.removeEventListener('scroll', check)
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
    const settleAt = () => {
      const pos = window.scrollY
      const h = holds().find((x) => Math.abs(x.pos - pos) <= 8)
      if (h) o.current.onSettled(h)
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
    lenis.on('scroll', () => {
      const pos = window.scrollY
      if (Math.abs(pos - lastPos) > 0.5) lastDir = pos > lastPos ? 1 : -1
      lastPos = pos
      window.clearTimeout(snapTimer)
      snapTimer = window.setTimeout(maybeSnap, 160)
    })
    const tick = (time: number) => lenis.raf(time * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)

    const triggers: Array<ScrollTrigger | undefined> = []
    const hasCover = Boolean(game.querySelector('[data-cover]'))
    const holds = (): Hold[] => {
      const out: Hold[] = hasCover ? [{ pos: 0, round: 0, kind: 'cover' }] : []
      for (let i = 0; i < count; i++) {
        const st = triggers[i]
        if (!st) continue
        const span = st.end - st.start
        out.push({ pos: Math.round(st.start + QUESTION_HOLD * span), round: i, kind: 'q' })
        if (o.current.isAnswered(i)) out.push({ pos: Math.round(st.start + REVEAL_HOLD * span), round: i, kind: 'r' })
      }
      out.push({ pos: Math.max(0, Math.round(endEl.getBoundingClientRect().top + window.scrollY - frameOffset(game))), round: count, kind: 'end' })
      return out
    }
    const scrollToPos = (pos: number, duration = 0.9) => {
      interacted = true
      lenis.scrollTo(pos, { duration, onComplete: settleAt })
    }
    api.current = {
      holds,
      goToRound: (r, d) => {
        const h = holds().find((x) => x.round === Math.min(Math.max(r, 0), count) && (x.kind === 'q' || x.kind === 'end'))
        if (h) scrollToPos(h.pos, d)
      },
      goToReveal: (r) => {
        const h = holds().find((x) => x.round === r && x.kind === 'r')
        if (h) scrollToPos(h.pos)
      },
      lock: (locked) => (locked ? lenis.stop() : lenis.start()),
    }

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
        act.style.setProperty('--draw', '0')
        act.style.setProperty('--reveal', '0')
        const tl = gsap.timeline({
          defaults: { ease: 'none' },
          scrollTrigger: {
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
        tl.to(draw, { v: 1, duration: 0.34, onUpdate: () => act.style.setProperty('--draw', draw.v.toFixed(3)) }, 0.16)
        // (c) the headline, then the statement, resolve to a sharp hold
        if (head) tl.fromTo(head, { opacity: 0, y: 44 }, { opacity: 1, y: 0, duration: 0.2, ease: 'expo.out' }, 0.22)
        // the statement resolves to a sharp hold with the answers
        if (qblock.length) tl.fromTo(qblock, { opacity: 0, y: 36, filter: 'blur(10px)' }, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.2, ease: 'expo.out' }, 0.36)
        // (d) the reveal bars extend
        tl.to(reveal, { v: 1, duration: 0.18, onUpdate: () => act.style.setProperty('--reveal', reveal.v.toFixed(3)) }, 0.7)
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
        },
      })
      triggers.push(master)
    }, game)

    ScrollTrigger.refresh()
    const onResize = () => ScrollTrigger.refresh()
    const tb = game.querySelector('.stance-top')
    const ro = typeof ResizeObserver !== 'undefined' && tb ? new ResizeObserver(() => ScrollTrigger.refresh()) : null
    if (tb) ro?.observe(tb)
    window.addEventListener('orientationchange', onResize)

    return () => {
      window.clearTimeout(snapTimer)
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
      })
      gsap.ticker.remove(tick)
      gsap.ticker.lagSmoothing(500, 33)
      lenis.destroy()
      api.current = { holds: () => [], goToRound: () => {}, goToReveal: () => {}, lock: () => {} }
    }
  }, [animated, count, gameRef])

  const holds = useCallback(() => api.current.holds(), [])
  const goToRound = useCallback((r: number, d?: number) => api.current.goToRound(r, d), [])
  const goToReveal = useCallback((r: number) => api.current.goToReveal(r), [])
  const lock = useCallback((l: boolean) => api.current.lock(l), [])
  return useMemo(() => ({ holds, goToRound, goToReveal, lock }), [holds, goToRound, goToReveal, lock])
}
