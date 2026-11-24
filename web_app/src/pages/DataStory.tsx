import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '../styles/folio.css'
import '../styles/stance.css'
import ProgressRail from '../components/stance/ProgressRail'
import PlaceControl from '../components/stance/PlaceControl'
import ScopeBar from '../components/stance/ScopeBar'
import SentenceHeading from '../components/stance/SentenceHeading'
import StoryScreenView from '../components/stance/StoryScreenView'
import { useActs, type Hold } from '../components/stance/useActs'
import { useRecentWrites } from '../components/stance/useRecentWrites'
import { useScreenKeys } from '../components/stance/useScreenKeys'
import { useStoryData } from '../components/stance/useStoryData'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { STATE_CODES } from '../lib/usStates'
import {
  DATA_CENTER_STORY,
  challengePath,
  screenText,
  scopeQuery,
  stopLabel,
  storyPlaceDisplay,
  storyScopeLabel,
  type StoryScope,
} from '../utils/dataStory'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

// Topics with a story. A story (and a challenge) needs meeting recordings or transcripts behind it: figure-only data, such as
// census measures, is shown under Explore, not here.
const STORIES: Record<string, { title: string; topic: string; pack: string; screens: typeof DATA_CENTER_STORY }> = {
  'data-centers': { title: 'Data Center Story', topic: 'data centers', pack: 'data-centers', screens: DATA_CENTER_STORY },
}

/** The topics that have a story: the options of the topic blank. */
export const STORY_TOPICS = Object.entries(STORIES).map(([value, s]) => ({ value, label: s.topic }))

/** The data story at `/stories/:storyId`: pinned screens driven by scroll (the challenge's engine), or stacked panels. */
export default function DataStory() {
  const { storyId = 'data-centers' } = useParams()
  const story = STORIES[storyId]
  const [sp, setSp] = useSearchParams()
  const reduced = usePrefersReducedMotion()
  const navigate = useNavigate()

  // The scope lives in the URL: label, queries and charts all read it from here.
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const scope: StoryScope = useMemo(() => ({ stateCode, stateName, city }), [stateCode, stateName, city])
  const screenParam = sp.get('screen') ?? ''

  const screens = useMemo(() => story?.screens ?? [], [story])
  const n = screens.length
  const { data, status, refetch } = useStoryData(stateCode, city)
  const texts = useMemo(() => screens.map((s) => screenText(s, data, status, scope)), [screens, data, status, scope])

  const wide = useMediaQuery('(min-width: 768px)')
  const animated = !reduced && wide
  const rootRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  const [placeOpen, setPlaceOpen] = useState(false)

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
  }, [story])

  const activeRef = useRef(0)
  const ready = useRef(false)
  const lastWritten = useRef<string | null>(null)
  const recent = useRecentWrites()
  const placeOpenRef = useRef(false)
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
  const onActive = useCallback(
    (i: number) => {
      if (!ready.current || (i === activeRef.current && lastWritten.current != null)) return
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
    },
    [setSp, idAt, recent],
  )
  /** After a keyboard move, focus lands on the settled screen's Continue button so the next key press carries on. */
  const onSettled = useCallback((h: Hold) => {
    if (placeOpenRef.current) return
    const ae = document.activeElement as HTMLElement | null
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.closest('.stance-place'))) return
    const panel = rootRef.current?.querySelector<HTMLElement>(`[data-panel="${h.round}"]`)
    if (viaKeyboard.current) {
      panel?.querySelector<HTMLElement>('.stance-next')?.focus({ preventScroll: true })
    } else if (panel && (ae == null || ae === document.body || !panel.contains(ae))) {
      // After wheel or pointer scrolling nothing visibly takes focus, but the screen becomes the starting point for Tab, so
      // the next Tab stop is its Continue control (the first control in the screen).
      panel.focus({ preventScroll: true })
    }
  }, [])

  const acts = useActs({
    animated,
    smooth: !reduced,
    gameRef: rootRef,
    // The last screen (your turn) is the untimed end panel, like the challenge's end screen.
    count: Math.max(0, n - 1),
    isAnswered: () => false,
    onActive,
    onSettled,
  })

  // Land on the screen named in the URL once the screens exist, then start following the scroll.
  useEffect(() => {
    if (n === 0) return
    ready.current = false
    // The story opens on its first screen's hold, with the headline and chart in place, not on the empty start of its timeline.
    const at = Math.max(0, screens.findIndex((s) => s.id === screenParam))
    const h = acts.holds().find((x) => x.round === at && x.kind !== 'r')
    if (h && (at > 0 || animated)) window.scrollTo({ top: h.pos, behavior: 'auto' })
    activeRef.current = at
    setActive(at)
    lastWritten.current = screens[at]?.id ?? null
    const id = requestAnimationFrame(() => requestAnimationFrame(() => (ready.current = true)))
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n, animated])

  // A screen in the URL that changed from outside (a link, the back button) moves the page.
  useEffect(() => {
    if (!ready.current || !screenParam || lastWritten.current === screenParam || recent.has(screenParam)) return
    const at = screens.findIndex((s) => s.id === screenParam)
    if (at >= 0 && at !== activeRef.current) acts.goToRound(at)
  }, [screenParam, screens, acts, recent])

  const goTo = acts.goToRound
  useEffect(() => acts.lock(placeOpen), [placeOpen, acts])
  placeOpenRef.current = placeOpen

  useScreenKeys({
    next: () => goTo(Math.min(activeRef.current + 1, n - 1)),
    prev: () => goTo(Math.max(activeRef.current - 1, 0)),
    first: () => goTo(0),
    last: () => goTo(n - 1),
    enabled: !placeOpen,
  })

  const applyPlace = useCallback(
    (code: string | null, community: string | null) => {
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (code) next.set('state', code)
          else next.delete('state')
          if (code && community) next.set('city', community)
          else next.delete('city')
          return next
        },
        { replace: true },
      )
    },
    [setSp],
  )

  if (!story) {
    return (
      <div className="folio stance-game stance-message" style={HOUSE_STYLE} role="alert">
        <h1>There is no such story.</h1>
        <p>
          <Link to={`/stories${scopeQuery(scope)}`}>See all data stories</Link>
        </p>
      </div>
    )
  }

  const label = storyScopeLabel(scope)
  const links = {
    challenge: challengePath(story.pack, scope),
    dataCenters: `/data-centers${scopeQuery(scope)}`,
    decisions: `/browse-topics${scopeQuery(scope)}`,
  }
  const labels = screens.map((s, i) => stopLabel(s, texts[i]!))

  return (
    <div className="folio stance-game stance-story" style={HOUSE_STYLE} ref={rootRef} data-mode={animated ? 'pinned' : 'stacked'}>
      <ScopeBar
        backTo={`/stories${scopeQuery(scope)}`}
        backLabel="← Data stories"
        title={story.title}
        label={label}
        heading={
          <SentenceHeading
            template={['What did ', { blank: 'place' }, ' say about ', { blank: 'topic' }, '?']}
            blanks={[
              {
                id: 'place',
                label: 'Place',
                value: stateCode ?? '',
                display: storyPlaceDisplay(scope),
                options: [],
                onChange: () => {},
                control: (
                  <PlaceControl
                    variant="blank"
                    display={storyPlaceDisplay(scope)}
                    stateCode={stateCode}
                    city={city}
                    open={placeOpen}
                    onOpenChange={setPlaceOpen}
                    onApply={applyPlace}
                  />
                ),
              },
              {
                id: 'topic',
                label: 'Topic',
                value: storyId,
                display: story.topic,
                options: STORY_TOPICS,
                onChange: (v) => navigate(`/stories/${encodeURIComponent(v)}${scopeQuery(scope)}`),
              },
            ]}
          />
        }
        stateCode={stateCode}
        stateName={stateName}
        city={city}
        current={screens[active]?.eyebrow ?? ''}
        placeOpen={placeOpen}
        onPlaceOpenChange={setPlaceOpen}
        onApply={applyPlace}
      />
      <p className="folio-sr-only" aria-live="polite">
        {screens[active] ? `${screens[active]!.eyebrow}. ${texts[active]!.headline}` : ''}
      </p>
      <div className="stance-body">
        <div className="stance-acts">
          {screens.map((s, i) => (
            <StoryScreenView
              key={s.id}
              screen={s}
              index={i}
              text={texts[i]!}
              data={data}
              status={status}
              scope={scope}
              active={active === i}
              nextLabel={i < n - 1 ? screens[i + 1]!.eyebrow : null}
              onPrev={i > 0 ? () => goTo(i - 1) : undefined}
              onNext={() => goTo(i + 1)}
              onBroaden={applyPlace}
              onRetry={() => s.chart && refetch(s.chart)}
              links={links}
            />
          ))}
        </div>
        <ProgressRail labels={labels} active={active} onJump={goTo} navLabel="Story screens" />
      </div>
      <p className="stance-keys">Keys: PageDown, Space or ↓ next · PageUp, Shift+Space or ↑ back · Home and End jump to the ends</p>
    </div>
  )
}
