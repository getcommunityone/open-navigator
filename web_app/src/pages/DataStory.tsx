import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import '../styles/folio.css'
import '../styles/stance.css'
import { errorStatus, fetchChoiceResults, fetchStancePack, postStanceChoice, type ChoiceMoment, type ChoiceResults } from '../api/stance'
import FloatingNext from '../components/stance/FloatingNext'
import ProgressPips from '../components/stance/ProgressPips'
import PlaceControl from '../components/stance/PlaceControl'
import ScopeBar from '../components/stance/ScopeBar'
import SentenceHeading from '../components/stance/SentenceHeading'
import SoundToggle from '../components/stance/SoundToggle'
import StoryScreenView from '../components/stance/StoryScreenView'
import { NextStoryCard, StoryBottomBar, StoryDots, StoryTopBar } from '../components/stance/StoryProgress'
import { useStoryStatements } from '../components/stance/useStoryStatements'
import { QuestionScreen, VerdictScreen, type VoteState } from '../components/stance/StoryVoteScreens'
import { actsMode, useActs, type Hold } from '../components/stance/useActs'
import { useRecentWrites } from '../components/stance/useRecentWrites'
import { useScreenKeys } from '../components/stance/useScreenKeys'
import { useStoryData } from '../components/stance/useStoryData'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { STATE_CODES } from '../lib/usStates'
import {
  screenText,
  scopeQuery,
  stopLabel,
  storyPlaceDisplay,
  storyScopeLabel,
  storyScreenIndex,
  type StoryScope,
  STORIES,
} from '../utils/dataStory'
import { fetchDataCenterPositions, type DataCenterPositionsResponse } from '../api/dataCenters'
import { storyHeroPoints } from '../utils/heroPoints'
import { fetchTopicCaptionFacts } from '../api/topics'
import { captionSubhead, captionText, pickCaption } from '../utils/storyCaption'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { NUDGE_ENTRANCE_MS } from '../utils/idleNudge'
import { SOUND_EVENT, createSoundBoard } from '../utils/stanceSound'
import { getStancePlayerId } from '../utils/stancePlayer'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { nextStoryLink } from '../utils/storyNav'
import { optionLabel, questionText } from '../utils/storyQuestion'

// The stories registry lives in utils/dataStory (STORIES), so the home page can list stories without this page's chunk.
export const STORY_TOPICS = Object.entries(STORIES).map(([value, s]) => ({ value, label: s.topic }))

/** How long a first answer stays on screen, locked, before the story moves on. */
const ANSWER_HOLD_MS = 700

/**
 * The data story at `/stories/:storyId`. It opens on an overview of the record, shows who spoke up and the rest one screen
 * at a time, and closes on the topic question after that context (#950 / #915). Screens are pinned and driven by the scroll
 * on a wide screen and snap one per swipe on a phone (see `useActs`). Under reduced motion (which a phone's battery saver
 * also turns on) the story keeps one screen at a time on every width and each screen cross-fades in: opacity only, nothing
 * slides, scales or loops (#930).
 */
export default function DataStory() {
  const { storyId = 'data-centers' } = useParams()
  const story = STORIES[storyId]
  const [sp, setSp] = useSearchParams()
  const reduced = usePrefersReducedMotion()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const playerId = useMemo(() => getStancePlayerId(), [])

  // The scope lives in the URL: label, queries and charts all read it from here.
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const scope: StoryScope = useMemo(() => ({ stateCode, stateName, city }), [stateCode, stateName, city])
  const scopeKey = `${stateCode ?? ''}|${city ?? ''}`
  const shownIds = useRef<string[]>([])
  const screenParam = sp.get('screen') ?? ''

  const allScreens = useMemo(() => story?.screens ?? [], [story])
  const { data, status, refetch } = useStoryData(stateCode, city)
  // The caption's facts (#1125), keyed on the scope so the label and the numbers move together.
  const captionQ = useQuery({
    queryKey: ['caption-facts', storyId, stateCode ?? '', city ?? ''],
    queryFn: () => fetchTopicCaptionFacts(storyId, stateCode, city),
    enabled: Boolean(story),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  // --- the question and the reader's two answers ------------------------------------------------------------------------
  const packId = story?.pack ?? ''
  // National AI-reading totals for the header's points (#1134); shares its cache with the home hero's conclusion query.
  const nationalPositionsQ = useQuery({
    queryKey: ['story-conclusion', 'positions', 'national'],
    queryFn: () => fetchDataCenterPositions({}),
    enabled: Boolean(story?.conclusion),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const packQ = useQuery({ queryKey: ['stance', 'pack', packId], queryFn: () => fetchStancePack(packId), enabled: Boolean(story), retry: 1 })
  const question = packQ.data?.question ?? null
  // A screen with nothing on record for the place is left out of the story once its data has loaded (#1002): no step,
  // no pip, not reached by Next. Only chart screens drop (Overview and the question screens stay); a screen still
  // loading stays until known.
  // The Overview states the page's caption when it is a conclusion (#1134), the same one as the title and the home hero.
  const overviewCaption = useMemo(() => {
    const c = pickCaption(storyId, captionQ.data, scope)
    return { kind: c.kind, text: captionText(c, story?.topic ?? storyId) }
  }, [storyId, captionQ.data, scope, story])
  const allTexts = useMemo(
    () => allScreens.map((s) => screenText(s, data, status, scope, question, overviewCaption)),
    [allScreens, data, status, scope, question, overviewCaption],
  )
  const keep = allScreens.map((s, i) => s.kind !== 'chart' || !allTexts[i]!.empty)
  const keepKey = keep.join()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const screens = useMemo(() => allScreens.filter((_, i) => keep[i]), [allScreens, keepKey])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const texts = useMemo(() => allTexts.filter((_, i) => keep[i]), [allTexts, keepKey])
  const n = screens.length
  // The statements each contested screen asks (#981), and the reader's answers to them.
  const statements = useStoryStatements(packQ.data, playerId, stateCode, city)
  const choiceKey = useMemo(() => ['stance', 'choices', packId, stateCode ?? '', city ?? '', playerId], [packId, stateCode, city, playerId])
  const choiceQ = useQuery({
    queryKey: choiceKey,
    queryFn: () => fetchChoiceResults(packId, { stateCode, placeName: city ?? undefined, playerId }),
    enabled: Boolean(question),
    retry: 1,
    placeholderData: keepPreviousData,
  })
  // Answers the API has confirmed on this visit; they win over what was fetched before them.
  const [stored, setStored] = useState<Partial<Record<ChoiceMoment, string>>>({})
  const before = stored.before ?? choiceQ.data?.your.before ?? null
  const after = stored.after ?? choiceQ.data?.your.after ?? null
  const [pending, setPending] = useState<VoteState['pending']>(null)
  const [voteError, setVoteError] = useState<VoteState['error']>(null)
  const [fresh, setFresh] = useState(false)

  // One sound board, shared with the challenge's setting. Soft page-turn / idle cues while reading; lock when an answer lands (#966).
  const board = useMemo(() => createSoundBoard({ attach: false }), [])
  useEffect(() => {
    board.attach()
    return () => board.dispose()
  }, [board])
  const [soundOn, setSoundOn] = useState(board.enabled)
  // The site menu can switch sound too (on phones the header has no sound button, #1017).
  useEffect(() => {
    const on = (e: Event) => {
      const next = Boolean((e as CustomEvent<boolean>).detail)
      if (next !== board.enabled) board.setEnabled(next)
      setSoundOn(next)
    }
    window.addEventListener(SOUND_EVENT, on)
    return () => window.removeEventListener(SOUND_EVENT, on)
  }, [board])
  const toggleSound = () => {
    const next = !soundOn
    board.setEnabled(next)
    setSoundOn(next)
    // Preview so Sound on is audible immediately (Web Audio unlocks on this click).
    if (next) board.play('lock')
  }


  const wide = useMediaQuery('(min-width: 768px)')
  const mode = reduced ? 'snap' : actsMode(false, wide)
  const rootRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  // Two places open the place dialog: the sentence in the top bar and the "Where?" screen.
  const [placeOpen, setPlaceOpen] = useState(false)
  // The next-story card in view (#1102): the dots and the floating bar step aside so they don't sit over it or the footer.
  const [atEnd, setAtEnd] = useState(false)
  const dialogOpen = placeOpen
  // A reader who has stopped gets a calm cue on the screen's next step; first idle nudge plays a soft sound when sound is on (#966).
  useIdleNudge({
    rootRef,
    screen: `[data-panel="${active}"]`,
    resetKey: active,
    entranceMs: NUDGE_ENTRANCE_MS,
    onNudge: (first) => {
      if (first) board.play('open')
    },
  })

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
  }, [story])
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
      // Soft page-turn when the reader advances (silent until Web Audio is unlocked by a click/key) (#966).
      if (moved) board.play('open')
    },
    [setSp, idAt, recent, board],
  )
  /** After a keyboard move, focus lands on the settled screen's first answer or its Continue button so the next key press carries on. */
  const onSettled = useCallback((h: Hold) => {
    if (dialogOpenRef.current) return
    const ae = document.activeElement as HTMLElement | null
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.closest('.stance-place'))) return
    const panel = rootRef.current?.querySelector<HTMLElement>(`[data-panel="${h.round}"]`)
    if (viaKeyboard.current) {
      const target = panel?.querySelector<HTMLElement>('.stance-next') ?? panel?.querySelector<HTMLElement>('.stance-answers button:not(:disabled)')
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
    // The last screen (the question again) is the untimed end panel, like the challenge's end screen.
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
    const land = (behavior: ScrollBehavior) => {
      const h = acts.holds().find((x) => x.round === at && x.kind !== 'r')
      // The first screen on the flow layout is the top of the page. The page can arrive scrolled (a previous page's
      // offset, e.g. home's Data stories section), so the story always moves to its screen; before #991 it stayed put
      // at screen 0 and opened mid-way, on a screen that wasn't the active one.
      const target = at > 0 || mode === 'pinned' ? h?.pos : 0
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

  useScreenKeys({
    next: () => goTo(Math.min(activeRef.current + 1, n - 1)),
    prev: () => goTo(Math.max(activeRef.current - 1, 0)),
    first: () => goTo(0),
    last: () => goTo(n - 1),
    enabled: !dialogOpen,
  })

  // --- storing an answer -----------------------------------------------------------------------------------------------
  /** One POST. The answer carries the place given (the one in the URL unless the place has just been changed). */
  const store = useCallback(
    async (moment: ChoiceMoment, choice: string, code: string | undefined, community: string | null) => {
      if (!question) throw new Error('no question')
      const out = await postStanceChoice({
        player_id: playerId,
        pack_id: packId,
        question_id: question.question_id,
        moment,
        choice,
        state_code: code,
        place_name: code && community ? community : undefined,
      })
      setStored((s) => ({ ...s, [moment]: out.stance_choice_response.choice }))
      qc.setQueryData<ChoiceResults>(['stance', 'choices', packId, code ?? '', (code && community) || '', playerId], out.results)
      return out
    },
    [question, playerId, packId, qc],
  )
  const answer = useCallback(
    async (moment: ChoiceMoment, choice: string) => {
      if (!question || pending) return
      const first = (moment === 'before' ? before : after) == null
      board.play('lock')
      setPending({ moment, choice })
      setVoteError(null)
      try {
        await store(moment, choice, stateCode, city)
        if (moment === 'after') setFresh(true)
        // Legacy: a first "before" answer on an opening question screen carried the reader on. The story no longer opens on
        // that screen (#950); keep the advance only if the active panel is still a question kind.
        if (moment === 'before' && first) {
          const kind = screens[activeRef.current]?.kind
          if (kind === 'question') window.setTimeout(() => activeRef.current === 0 && goTo(1), reduced ? 0 : ANSWER_HOLD_MS)
        }
      } catch (err) {
        const message =
          errorStatus(err) === 429
            ? 'Too many answers just now. Wait a little, then try again. Your answer was not saved.'
            : 'Your answer could not be saved. Check your connection, then try again.'
        setVoteError({ moment, choice, message })
      } finally {
        setPending(null)
      }
    },
    [question, pending, before, after, board, store, stateCode, city, goTo, reduced, screens],
  )

  const answersRef = useRef({ before, after })
  answersRef.current = { before, after }
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
      // The question comes before the place, so an answer already given is stored again with the place the reader then names
      // (otherwise it could never count in that state's or community's split). Broadening to the country changes nothing stored.
      if (code && (code !== stateCode || (community ?? null) !== city)) {
        for (const moment of ['before', 'after'] as const) {
          const choice = answersRef.current[moment]
          if (choice) void store(moment, choice, code, community).catch(() => {})
        }
      }
    },
    [setSp, store, stateCode, city],
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
  // #993 / #1125: the title is the strongest statement the place's record supports (utils/storyCaption), from the caption
  // facts for exactly this scope; the home hero and the Overview state the same one. #1134: with its scoped subhead and
  // numbered points (the place's own figures where it has them, else national ones marked "Nationally:").
  const title = pickCaption(storyId, captionQ.data, scope)
  const subhead = captionSubhead(title, storyId, scope)
  const scopedPositions = data.positions as DataCenterPositionsResponse | null | undefined
  const points = storyHeroPoints(scope.stateName ? nationalPositionsQ.data : scopedPositions, scope.stateName ? scopedPositions : null, scope.stateName ? label : null)
  const links = {
    dataCenters: `/data-centers${scopeQuery(scope)}`,
    decisions: `/browse-topics${scopeQuery(scope)}`,
  }
  const labels = screens.map((s, i) => stopLabel(s, texts[i]!))
  // The end of the story leads on (#1102): the next live story, or every data story, keeping the place.
  const onward = nextStoryLink(storyId, scopeQuery(scope))
  const vote: VoteState = {
    question,
    loading: packQ.isLoading,
    failed: packQ.isError || (packQ.isSuccess && !question),
    onRetryLoad: () => void packQ.refetch(),
    before,
    after,
    pending,
    error: voteError,
    onAnswer: (moment, choice) => void answer(moment, choice),
  }
  const placeBlank = (open: boolean, onOpenChange: (o: boolean) => void, display = storyPlaceDisplay(scope)) => (
    <PlaceControl
      variant="blank"
      display={display}
      stateCode={stateCode}
      city={city}
      open={open}
      onOpenChange={onOpenChange}
      onApply={applyPlace}
    />
  )

  return (
    <div
      className="folio stance-game stance-story"
      style={HOUSE_STYLE}
      ref={rootRef}
      data-mode={mode}
      data-fade={reduced ? '' : undefined}
      data-sbar={wide ? undefined : ''}
    >
      {wide && <StoryTopBar active={active} count={n} />}
      <ScopeBar
        backTo={`/stories${scopeQuery(scope)}`}
        backLabel="← Data stories"
        title={story.title}
        label={label}
        heading={
          <>
          <SentenceHeading
            template={title.template}
            blanks={[
              {
                id: 'place',
                label: 'Place',
                value: stateCode ?? '',
                display: title.place,
                options: [],
                onChange: () => {},
                control: placeBlank(placeOpen, setPlaceOpen, title.place),
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
          {subhead && <p className="stance-title-subhead">{subhead}</p>}
          {title.basis && <p className="stance-title-basis">{title.basis}</p>}
          {points.length > 0 && (
            <ol className="stance-title-points" aria-label={scope.stateName ? `What the record shows for ${label}` : 'What the record shows, nationally'}>
              {points.map((pt) => (
                <li key={pt.icon}>
                  <span className="stance-title-point-n">{pt.n}</span>
                  <span>
                    <strong>{pt.title}</strong> {pt.line}
                  </span>
                </li>
              ))}
            </ol>
          )}
          </>
        }
        stateCode={stateCode}
        stateName={stateName}
        city={city}
        current={screens[active]?.eyebrow ?? ''}
        extra={
          <span className="stance-top-actions">
            <SoundToggle on={soundOn} onToggle={toggleSound} />
            {/* Close (#1017): back to the home page's stories, keeping the place. */}
            <Link to={`/${scopeQuery(scope)}#data-stories`} className="folio-btn stance-close" aria-label="Close story" title="Close">
              <span aria-hidden="true">×</span>
            </Link>
          </span>
        }
        progress={<ProgressPips count={n} active={active} />}
        placeOpen={placeOpen}
        onPlaceOpenChange={setPlaceOpen}
        onApply={applyPlace}
      />
      <p className="folio-sr-only" aria-live="polite">
        {screens[active] ? `${screens[active]!.eyebrow}. ${texts[active]!.headline}` : ''}
      </p>
      <div className="stance-body">
        {/* Keyed by which screens are in the story: when empty screens drop out (#1002) the list is rebuilt whole, because
            the pinned layout has moved the old screens into its own wrappers and React can't remove them one by one. */}
        <div className="stance-acts" key={keepKey}>
          {screens.map((s, i) => {
            const common = {
              screen: s,
              index: i,
              text: texts[i]!,
              scope,
              active: active === i,
              nextLabel: i < n - 1 ? screens[i + 1]!.eyebrow : null,
              onPrev: i > 0 ? () => goTo(i - 1) : undefined,
              onNext: () => goTo(i + 1),
            }
            if (s.kind === 'question') return <QuestionScreen key={s.id} {...common} vote={vote} />
            if (s.kind === 'verdict') {
              return (
                <VerdictScreen
                  key={s.id}
                  {...common}
                  vote={vote}
                  results={choiceQ.data}
                  resultsFailed={choiceQ.isError}
                  fresh={fresh}
                  links={links}
                />
              )
            }
            return (
              <StoryScreenView
                key={s.id}
                {...common}
                data={data}
                status={status}
                onBroaden={applyPlace}
                onRetry={() => s.chart && refetch(s.chart)}
                stance={statements.get(s.id)}
                question={s.kind === 'overview' && question ? questionText(question, scope) : null}
                said={s.kind === 'overview' ? optionLabel(question, before) : null}
              />
            )
          })}
        </div>
        {/* After the last screen, outside the screens ([data-panel]) the scroller counts: the way on to the next story. */}
        <NextStoryCard href={onward.href} label={onward.label} isStory={onward.next != null} onInView={setAtEnd} />
        {/* Wide screens: numbered dots down the left edge; they move with goTo, like Next and the keys. */}
        {wide && <StoryDots labels={labels} active={active} onJump={goTo} away={atEnd} />}
      </div>
      {/* Phones get the bottom bar instead, which always shows Next; the floating bar would sit on top of it. */}
      {wide ? (
        !atEnd && <FloatingNext rootRef={rootRef} screen={`[data-panel="${active}"]`} />
      ) : (
        <StoryBottomBar
          active={active}
          count={n}
          nextLabel={active < n - 1 ? (screens[active + 1]?.eyebrow ?? null) : null}
          onNext={() => goTo(Math.min(activeRef.current + 1, n - 1))}
          storyHref={onward.href}
          storyLabel={onward.label}
          storyIsNext={onward.next != null}
        />
      )}
      <p className="stance-keys">Keys: PageDown, Space or ↓ next · PageUp, Shift+Space or ↑ back · Home and End jump to the ends</p>
    </div>
  )
}
