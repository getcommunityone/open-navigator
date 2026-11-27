import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import '../styles/folio.css'
import '../styles/stance.css'
import { errorStatus, fetchChoiceResults, fetchStancePack, postStanceChoice, type ChoiceMoment, type ChoiceResults } from '../api/stance'
import StoryNextButton from '../components/stance/StoryNextButton'
import ProgressPips from '../components/stance/ProgressPips'
import PlaceControl from '../components/stance/PlaceControl'
import ScopeBar from '../components/stance/ScopeBar'
import ScopeNote from '../components/stance/ScopeNote'
import SentenceHeading from '../components/stance/SentenceHeading'
import StoryScreenView from '../components/stance/StoryScreenView'
import StoryScreenFrame from '../components/stance/StoryScreenFrame'
import UpcomingPanel from '../components/stance/UpcomingPanel'
import CoverageLine from '../components/stance/CoverageLine'
import SitesTimelinePanel from '../components/stance/SitesTimelinePanel'
import { fetchSitesTimeline } from '../api/sitesTimeline'
import { timelineHeadline } from '../utils/siteTimeline'
import { useTopicUpcoming } from '../hooks/useTopicUpcoming'
import { upcomingHeadline } from '../utils/topicUpcoming'
import OutcomesChain from '../components/stance/OutcomesChain'
import { useTopicOutcomes } from '../hooks/useTopicOutcomes'
import { outcomesHeadline } from '../utils/topicOutcomes'
import { StoryBottomBar } from '../components/stance/StoryProgress'
import StoryClose from '../components/stance/StoryClose'
import { useStoryStatements } from '../components/stance/useStoryStatements'
import { QuestionScreen, VerdictScreen, type VoteState } from '../components/stance/StoryVoteScreens'
import { useStoryScreens } from '../components/stance/useStoryScreens'
import { useStoryData } from '../components/stance/useStoryData'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { STATE_CODES } from '../lib/usStates'
import {
  chartScopeLabel,
  contextSourceFor,
  screenText,
  scopeQuery,
  storyPlaceDisplay,
  storyScopeLabel,
  type StoryScope,
  STORIES,
} from '../utils/dataStory'
import { fetchDataCenterPositions, type DataCenterPositionsResponse } from '../api/dataCenters'
import { storyHeroPoints } from '../utils/heroPoints'
import { fetchTopicCaptionFacts } from '../api/topics'
import PositionsSummary from '../components/stance/PositionsSummary'
import { disagreementLine, recordedEvidence } from '../utils/stanceEvidence'
import { captionSubhead, captionText, pickCaption, withTopicBlank } from '../utils/storyCaption'
import '../styles/story-actions.css'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { NUDGE_ENTRANCE_MS } from '../utils/idleNudge'
import { SOUND_EVENT, createSoundBoard } from '../utils/stanceSound'
import { getStancePlayerId } from '../utils/stancePlayer'
import { nextStoryLink, storyCloseHref, storyStartHref, storyTopicOptions } from '../utils/storyNav'
import { optionLabel, questionText } from '../utils/storyQuestion'
import { useStoryScope } from '../hooks/useStoryScope'
import { useTopicStories } from '../hooks/useTopicStories'
import { scopePlaceName, splitCaptionAtPlace, splitTextAtPlace } from '../utils/captionPlace'


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
  // The URL keeps the place asked; the story speaks for the level with enough meetings (#1285, `useStoryScope`): a city
  // with fewer than 5 steps up to its state, a state with fewer to the country, and a note under the bar says why.
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const askedState = STATE_CODES.includes(rawState) ? rawState : undefined
  const askedCity = askedState ? (sp.get('city') ?? '').trim() || null : null
  const askedQuery = scopeQuery({ stateCode: askedState, city: askedCity })
  const placeScope = useStoryScope(storyId, story?.topic ?? storyId, askedState, askedCity)
  const stateCode = placeScope.effective.stateCode
  const stateName = placeScope.effective.stateName
  const city = placeScope.effective.city
  const scope: StoryScope = useMemo(() => ({ stateCode, stateName, city }), [stateCode, stateName, city])
  const scopeKey = `${stateCode ?? ''}|${city ?? ''}`
  const screenParam = sp.get('screen') ?? ''

  const allScreens = useMemo(() => story?.screens ?? [], [story])
  const { data, status, refetch } = useStoryData(stateCode, city)
  // The live stories (#1133), so the end of the story leads on to the next one, topic stories included.
  const { live: liveList } = useTopicStories()
  // The caption's facts (#1125), keyed on the scope so the label and the numbers move together.
  const captionQ = useQuery({
    queryKey: ['caption-facts', storyId, stateCode ?? '', city ?? ''],
    queryFn: () => fetchTopicCaptionFacts(storyId, stateCode, city),
    enabled: Boolean(story),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  // What's coming up (#1302), for the Coming up screen's headline; the panel reads the same cache entry.
  const upcomingQ = useTopicUpcoming(storyId, stateCode, city)
  // What happened next (#1314), for the chain screen's headline; the panel reads the same cache entry.
  const outcomesQ = useTopicOutcomes(storyId, stateCode, city)
  // Data centers over time (#1348): sites narrow by state only, so a city's story reads its state (the label says so).
  const timelineQ = useQuery({
    queryKey: ['data-centers', 'sites-timeline', stateCode ?? ''],
    queryFn: () => fetchSitesTimeline(stateCode),
    enabled: storyId === 'data-centers',
    staleTime: 10 * 60_000,
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
    () =>
      allScreens.map((s) => {
        const t = screenText(s, data, status, scope, question, overviewCaption)
        // #1330: where officials sided against the public, the Who spoke up screen headlines it (the count is in its panel).
        if (s.id !== 'voices' || t.empty || t.failed) return t
        const dis = disagreementLine(recordedEvidence(captionQ.data), scope.stateName ? `In ${storyScopeLabel(scope)}` : 'Across America')
        return dis ? { ...t, headline: dis } : t
      }),
    [allScreens, data, status, scope, question, overviewCaption, captionQ.data],
  )
  // A chart screen with nothing on record drops out (#1002); so does Over time once it knows no site has a date (#1348).
  const timelineEmpty = timelineQ.isSuccess && timelineQ.data.available && (timelineQ.data.dated ?? 0) === 0
  const keep = allScreens.map((s, i) => (s.kind === 'timeline' ? !timelineEmpty : s.kind !== 'chart' || !allTexts[i]!.empty))
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
  // Sound is set in Settings or the site menu (#1319); follow it live.
  useEffect(() => {
    const on = (e: Event) => {
      const next = Boolean((e as CustomEvent<boolean>).detail)
      if (next !== board.enabled) board.setEnabled(next)
    }
    window.addEventListener(SOUND_EVENT, on)
    return () => window.removeEventListener(SOUND_EVENT, on)
  }, [board])


  // Two places open the place dialog: the sentence in the top bar and the "Where?" screen.
  const [placeOpen, setPlaceOpen] = useState(false)
  const dialogOpen = placeOpen
  // The screen machine (#1224): landing, ?screen= sync, the cover, keys, swipe, re-aimed jumps (#1208) and focus, shared
  // with the topic stories.
  const { rootRef, wide, mode, active, activeRef, goTo } = useStoryScreens({
    screens,
    screenParam,
    setSp,
    scopeKey,
    resetKey: story,
    dialogOpen,
    reduced,
    // Soft page-turn when the reader advances (silent until Web Audio is unlocked by a click/key) (#966).
    onMove: () => board.play('open'),
  })
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
  // The title names another place (a broader scope's conclusion, or nationally the leading state): the scope's place control
  // goes in this line, on its name, else as a "Showing [place]" lead (#1234, as on the home card).
  const titleNamesScope = splitCaptionAtPlace(title, story.topic, scope) != null
  const subheadPlace = titleNamesScope
    ? null
    : (splitTextAtPlace(subhead, scopePlaceName(scope)) ?? { before: 'Showing ', place: scopePlaceName(scope), after: subhead ? `. ${subhead}` : '.' })
  const scopedPositions = data.positions as DataCenterPositionsResponse | null | undefined
  // #1289: with too little on record to say which way the place leans, the editorial points ("Communities are saying no.")
  // would claim the lean the title just declined to; the basis states the facts instead.
  const points =
    title.kind === 'insufficient'
      ? []
      : storyHeroPoints(scope.stateName ? nationalPositionsQ.data : scopedPositions, scope.stateName ? scopedPositions : null, scope.stateName ? label : null)
  const links = {
    dataCenters: `/data-centers${scopeQuery(scope)}`,
    decisions: `/browse-topics${scopeQuery(scope)}`,
  }
  // The progress segments' names (#1192): the screen's own word, "3 of 11: Sites", as the top bar shows it.
  const labels = screens.map((s) => s.eyebrow)
  // The end of the story leads on (#1102): the next live story, or every data story, keeping the place.
  const onward = nextStoryLink(storyId, scopeQuery(scope), liveList)
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
  // The opening's subhead, basis and points (#1282) sit in Overview's left column, under its headline: Overview is screen 1.
  const overviewLead = (
    <div className="stance-overview-lead">
      {(subhead || subheadPlace) && (
        // A div, not a p: the place control's dialog is a div.
        <div className="stance-title-subhead">
          {/* A broader scope's title (#1222): the place in scope is named, as the place control, in this line instead. */}
          {subheadPlace ? (
            <>
              {subheadPlace.before}
              {placeBlank(placeOpen, setPlaceOpen, subheadPlace.place)}
              {subheadPlace.after}
            </>
          ) : (
            subhead
          )}
        </div>
      )}
      {title.basis && <p className="stance-title-basis">{title.basis}</p>}
      {/* #1348: the counts above are counts of our recordings; say how many governments and meetings that is. */}
      <CoverageLine scope={scope} />
      {/* #1330: where officials sided against the public, with a tap through to those meetings. */}
      {storyId === 'data-centers' && <PositionsSummary scope={scope} only="disagreement" />}
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
    </div>
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
      <ScopeBar
        backTo={`/stories${scopeQuery(scope)}`}
        backLabel="← Data stories"
        // The one exit (#1234, owner 2026-11-27): Close (×) top right, back to the home page with the place kept. The bar
        // drops "← Data stories" and the "Showing:" row; the title's place control is the place switcher.
        note={
          placeScope.resolved.reason ? (
            // Why the story shows a wider place than the one asked (#1285); the URL keeps the reader's choice.
            <ScopeNote short={placeScope.resolved.short ?? placeScope.resolved.reason} full={placeScope.resolved.reason} level={placeScope.resolved.level} />
          ) : undefined
        }
        close={<StoryClose to={storyCloseHref(storyId, askedQuery)} escape={!dialogOpen} />}
        title={story.title}
        label={label}
        heading={
          <>
          <SentenceHeading
            // A place blank that isn't the scope (nationally, the leading state) is plain text, not the place control (#1234).
            template={withTopicBlank(titleNamesScope ? title.template : title.template.map((p) => (typeof p !== 'string' && p.blank === 'place' ? title.place : p)), story.topic)}
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
                // Every live story (#1224); choosing one opens it on its Overview, keeping the place.
                options: storyTopicOptions(liveList, storyId, story.topic),
                onChange: (v) => navigate(storyStartHref(v, scopeQuery(scope))),
              },
            ]}
          />
          </>
        }
        stateCode={stateCode}
        stateName={stateName}
        city={city}
        current={screens[active]?.eyebrow ?? ''}
        // One progress indicator per device (#1192): wide screens, these segments (a button per screen); phones, the bottom bar.
        progress={wide ? <ProgressPips count={n} active={active} labels={labels} onJump={goTo} /> : undefined}
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
            if (s.kind === 'outcomes') {
              return (
                <StoryScreenFrame
                  key={s.id}
                  id={s.id}
                  index={i}
                  active={active === i}
                  eyebrow={s.eyebrow}
                  headline={
                    outcomesQ.isPending
                      ? 'Loading what happened next…'
                      : outcomesQ.isError
                        ? 'What happened next could not be loaded right now.'
                        : outcomesHeadline(outcomesQ.data, story.topic, label)
                  }
                  context="From the meetings where it came up to what the public said, what local bodies did, the state bills and what is next. Tap a step to see its records."
                  nextLabel={common.nextLabel}
                  onNext={common.onNext}
                  onPrev={common.onPrev}
                  right={
                    <OutcomesChain
                      topic={storyId}
                      stateCode={stateCode}
                      city={city}
                      scopeLabel={label}
                      subject={story.topic}
                      actionWords={{ advanced: 'Approved', blocked: 'Denied' }}
                      dataCenterStory
                      onOpenScreen={(id) => {
                        const at = screens.findIndex((x) => x.id === id)
                        if (at >= 0) goTo(at)
                      }}
                    />
                  }
                />
              )
            }
            if (s.kind === 'timeline') {
              const sitesLabel = chartScopeLabel('sites', scope)
              return (
                <StoryScreenFrame
                  key={s.id}
                  id={s.id}
                  index={i}
                  active={active === i}
                  eyebrow={s.eyebrow}
                  kicker={`${s.kicker ?? 'For context'} · source: ${contextSourceFor(s.id)}`}
                  headline={
                    timelineQ.isPending
                      ? 'Loading data center sites over time…'
                      : timelineQ.isError
                        ? 'Data center sites over time could not be loaded right now.'
                        : timelineHeadline(timelineQ.data, sitesLabel)
                  }
                  context={`Each site appears in the year of its earliest date on record. Epoch AI sites move to operating as Epoch dates them; registry sites keep their status today.${scope.city && scope.stateName ? ` Sites are placed by state, so this shows ${scope.stateName}.` : ''}`}
                  nextLabel={common.nextLabel}
                  onNext={common.onNext}
                  onPrev={common.onPrev}
                  right={<SitesTimelinePanel res={timelineQ.data} scopeLabel={sitesLabel} stateCode={stateCode} active={active === i} reduced={reduced} />}
                />
              )
            }
            if (s.kind === 'upcoming') {
              return (
                <StoryScreenFrame
                  key={s.id}
                  id={s.id}
                  index={i}
                  active={active === i}
                  eyebrow={s.eyebrow}
                  headline={
                    upcomingQ.isPending
                      ? "Loading what's coming up…"
                      : upcomingQ.isError
                        ? "What's coming up could not be loaded right now."
                        : upcomingHeadline(upcomingQ.data, story.topic, label)
                  }
                  context="Scheduled meetings and public hearings from today on, with the agenda, livestream or notice to take part, and the state bills still open. Nothing here is estimated."
                  nextLabel={common.nextLabel}
                  onNext={common.onNext}
                  onPrev={common.onPrev}
                  right={
                    <UpcomingPanel
                      topic={storyId}
                      stateCode={stateCode}
                      city={city}
                      scopeLabel={label}
                      subject={story.topic}
                      basePath={`/stories/${storyId}`}
                    />
                  }
                />
              )
            }
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
                lead={s.kind === 'overview' ? overviewLead : null}
              />
            )
          })}
        </div>
        {/* After the last screen, outside the screens ([data-panel]) the scroller counts: the way on to the next story. */}
        {/* The story ends on its last screen (#1234): at most a small plain-text link on to another story, never a button.
            The home page is where readers pick the next story. */}
        {onward.next && (
          <p className="story-another">
            <Link to={onward.href}>Another story: {onward.next.title}</Link>
          </p>
        )}
      </div>
      {/* The one way forward (#1234, owner 2026-11-27): a green Next fixed at the bottom right on every screen, desktop and
          phone. Cover: starts the story; a screen: the next screen; the last screen: the next story, keeping the place. */}
      {active < n - 1 ? (
        <StoryNextButton label="Next" ariaLabel={`Next: ${screens[active + 1]?.eyebrow ?? ''}`.replace(/: $/, '')} onClick={() => goTo(Math.min(activeRef.current + 1, n - 1))} />
      ) : (
        <StoryNextButton label="Done" ariaLabel="Done: close the story" href={storyCloseHref(storyId, scopeQuery(scope))} quiet />
      )}
      {/* Phones: the bottom bar keeps Back and the progress dots; Next is the fixed button above, at its right end. */}
      {!wide && (
        <StoryBottomBar
          active={active}
          count={n}
          labels={labels}
          onJump={goTo}
          nextLabel={active < n - 1 ? (screens[active + 1]?.eyebrow ?? null) : null}
          onNext={() => goTo(Math.min(activeRef.current + 1, n - 1))}
          withNext={false}
          prevLabel={active > 0 ? (screens[active - 1]?.eyebrow ?? null) : null}
          onPrev={() => goTo(Math.max(activeRef.current - 1, 0))}
          storyHref={onward.href}
          storyLabel={onward.label}
          storyIsNext={onward.next != null}
        />
      )}
      <p className="stance-keys">Keys: PageDown, Space or ↓ next · PageUp, Shift+Space or ↑ back · Home and End jump to the ends</p>
    </div>
  )
}
