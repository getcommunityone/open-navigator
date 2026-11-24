import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '../styles/folio.css'
import '../styles/stance.css'
import {
  errorStatus,
  fetchStancePack,
  fetchStancePacks,
  fetchStanceResults,
  postStanceResponse,
  type PackResults,
  type StanceAnswer,
} from '../api/stance'
import Cover from '../components/stance/Cover'
import EndPanel from '../components/stance/EndPanel'
import ProgressRail from '../components/stance/ProgressRail'
import RoundPanel from '../components/stance/RoundPanel'
import ScopeBar from '../components/stance/ScopeBar'
import { useActs, type Hold } from '../components/stance/useActs'
import { useRecentWrites } from '../components/stance/useRecentWrites'
import { useScreenKeys } from '../components/stance/useScreenKeys'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { STATE_CODES } from '../lib/usStates'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { placeLabel } from '../utils/stanceGame'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { getStancePlayerId } from '../utils/stancePlayer'

const DEFAULT_PACK = 'data-centers'

interface Attempt {
  statementId: string
  answer: StanceAnswer
}

export default function Challenge() {
  const { packId = DEFAULT_PACK } = useParams()
  const [sp, setSp] = useSearchParams()
  const qc = useQueryClient()
  const reduced = usePrefersReducedMotion()
  const playerId = useMemo(() => getStancePlayerId(), [])

  // The scope lives in the URL: label, query and results all read it from here.
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const roundParam = Number.parseInt(sp.get('round') ?? '', 10)

  const packQ = useQuery({ queryKey: ['stance', 'pack', packId], queryFn: () => fetchStancePack(packId), retry: false })
  const pack = packQ.data
  const statements = useMemo(() => pack?.statements ?? [], [pack])
  const n = statements.length

  const resultsKey = useMemo(() => ['stance', 'results', packId, stateCode ?? '', city ?? '', playerId], [packId, stateCode, city, playerId])
  const resultsQ = useQuery({
    queryKey: resultsKey,
    queryFn: () => fetchStanceResults(packId, { stateCode, placeName: city ?? undefined, playerId }),
    enabled: Boolean(pack),
    retry: 1,
  })
  const packsQ = useQuery({ queryKey: ['stance', 'packs'], queryFn: fetchStancePacks, retry: false })
  const resultsById = useMemo(() => new Map((resultsQ.data?.statements ?? []).map((s) => [s.statement_id, s])), [resultsQ.data])

  // Answers the API has confirmed (from a POST that returned, or from the player's stored answers).
  const [confirmed, setConfirmed] = useState<Record<string, StanceAnswer>>({})
  useEffect(() => {
    const mine = (resultsQ.data?.statements ?? []).filter((s) => s.your_answer)
    if (mine.length) setConfirmed((c) => ({ ...c, ...Object.fromEntries(mine.map((s) => [s.statement_id, s.your_answer!])) }))
  }, [resultsQ.data])

  const [posting, setPosting] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, { message: string; attempt: Attempt } | null>>({})
  const [changing, setChanging] = useState<Record<string, boolean>>({})
  const [placeOpen, setPlaceOpen] = useState(false)

  // --- scrolling: pinned acts with Lenis, or plain stacked panels ------------------------------------------------------
  const wide = useMediaQuery('(min-width: 768px)')
  const animated = !reduced && wide
  const gameRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  // Offsets under the sticky site header and this page's own HUD bar, as CSS variables for the act height and anchors.
  useLayoutEffect(() => {
    const game = gameRef.current
    if (!game) return
    const measure = () => {
      const header = document.querySelector<HTMLElement>('.site-header')
      const top = game.querySelector<HTMLElement>('.stance-top')
      game.style.setProperty('--hdr', `${header?.offsetHeight ?? 0}px`)
      game.style.setProperty('--top-h', `${top?.offsetHeight ?? 96}px`)
    }
    measure()
    const top = game.querySelector('.stance-top')
    const ro = typeof ResizeObserver !== 'undefined' && top ? new ResizeObserver(measure) : null
    if (top) ro?.observe(top)
    window.addEventListener('resize', measure)
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [pack])
  const activeRef = useRef(0)
  const ready = useRef(false)
  const lastWritten = useRef<number | null>(null)
  const recent = useRecentWrites()
  const confirmedRef = useRef<Record<string, StanceAnswer>>({})
  const statementsRef = useRef(statements)
  statementsRef.current = statements
  confirmedRef.current = confirmed
  const placeOpenRef = useRef(false)
  const justAnswered = useRef<number | null>(null)

  const onActive = useCallback(
    (i: number) => {
      if (!ready.current || (i === activeRef.current && lastWritten.current != null)) return
      activeRef.current = i
      setActive(i)
      lastWritten.current = i + 1
      recent.note(String(i + 1))
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('round', String(i + 1))
          return next
        },
        { replace: true },
      )
    },
    [setSp, recent],
  )
  /** At a hold the keyboard player lands on a button: the answers when open, otherwise "Next round". */
  const onSettled = useCallback((h: Hold) => {
    if (placeOpenRef.current) return
    const ae = document.activeElement as HTMLElement | null
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.closest('.stance-place'))) return
    const act = gameRef.current?.querySelector<HTMLElement>(`[data-panel="${h.round}"]`)
    if (!act) return
    const target =
      act.querySelector<HTMLElement>('.stance-answers button:not(:disabled)') ??
      act.querySelector<HTMLElement>('.stance-next') ??
      act.querySelector<HTMLElement>('.stance-end-body button')
    target?.focus({ preventScroll: true })
  }, [])

  const acts = useActs({
    animated,
    smooth: !reduced,
    gameRef,
    count: pack ? n : 0,
    isAnswered: (i) => Boolean(confirmedRef.current[statementsRef.current[i]?.statement_id ?? '']),
    onActive,
    onSettled,
  })

  // Land on the round named in the URL once the acts exist, then start following the scroll.
  useEffect(() => {
    if (!pack) return
    ready.current = false
    if (Number.isFinite(roundParam) && roundParam > 1) {
      const target = Math.min(roundParam - 1, n)
      const h = acts.holds().find((x) => x.round === target && x.kind !== 'r')
      if (h) window.scrollTo({ top: h.pos, behavior: 'auto' })
      activeRef.current = target
      setActive(target)
    }
    const id = requestAnimationFrame(() => requestAnimationFrame(() => (ready.current = true)))
    return () => {
      cancelAnimationFrame(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pack, animated])

  // A round in the URL that changed from outside (a link, the back button) moves the page.
  useEffect(() => {
    if (!ready.current || !Number.isFinite(roundParam)) return
    if (lastWritten.current === roundParam || recent.has(String(roundParam))) return
    const target = Math.min(Math.max(roundParam - 1, 0), n)
    if (target !== activeRef.current) acts.goToRound(target)
  }, [roundParam, n, acts, recent])

  const goToRound = acts.goToRound
  useEffect(() => acts.lock(placeOpen), [placeOpen, acts])
  placeOpenRef.current = placeOpen

  // --- answering ------------------------------------------------------------------------------------------------------
  const submit = useCallback(
    async (attempt: Attempt) => {
      const { statementId, answer } = attempt
      setPosting(statementId)
      setErrors((e) => ({ ...e, [statementId]: null }))
      try {
        const out = await postStanceResponse({
          player_id: playerId,
          pack_id: packId,
          statement_id: statementId,
          answer,
          state_code: stateCode,
          place_name: stateCode && city ? city : undefined,
        })
        justAnswered.current = statementsRef.current.findIndex((x) => x.statement_id === statementId)
        setConfirmed((c) => ({ ...c, [statementId]: out.stance_response.answer }))
        setChanging((c) => ({ ...c, [statementId]: false }))
        qc.setQueryData<PackResults>(resultsKey, (old) =>
          old
            ? { ...old, statements: old.statements.map((s) => (s.statement_id === statementId ? { ...out.results, your_answer: out.stance_response.answer } : s)) }
            : old,
        )
        void qc.invalidateQueries({ queryKey: resultsKey })
      } catch (err) {
        const status = errorStatus(err)
        const message =
          status === 429
            ? 'Too many answers just now. Wait a little, then try again. Your answer was not saved.'
            : 'Your answer could not be saved. Check your connection, then try again.'
        setErrors((e) => ({ ...e, [statementId]: { message, attempt } }))
      } finally {
        setPosting(null)
      }
    },
    [playerId, packId, stateCode, city, qc, resultsKey],
  )

  // A confirmed answer is the interaction beat: carry the player to this round's reveal hold.
  useEffect(() => {
    const i = justAnswered.current
    if (i == null || i < 0) return
    justAnswered.current = null
    if (animated && i === activeRef.current) requestAnimationFrame(() => acts.goToReveal(i))
  }, [confirmed, animated, acts])

  // --- place ----------------------------------------------------------------------------------------------------------
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

  // --- keyboard -------------------------------------------------------------------------------------------------------
  // A, D and N answer; Enter goes on. Moving between rounds (PageDown/PageUp, Space, arrows, Home/End) is the shared hook.
  const live = useRef({ active, statements, confirmed, changing, posting })
  live.current = { active, statements, confirmed, changing, posting }
  const nextScreen = useCallback(() => {
    // On the cover (above the first round's question) going on starts the first round.
    const first = acts.holds().find((h) => h.kind === 'q')
    goToRound(first && window.scrollY < first.pos - 40 && live.current.active === 0 ? 0 : live.current.active + 1)
  }, [acts, goToRound])
  useScreenKeys({
    next: nextScreen,
    prev: () => goToRound(live.current.active - 1),
    first: () => window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }),
    last: () => goToRound(n),
    enabled: !placeOpen,
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      const L = live.current
      const k = e.key.toLowerCase()
      const map: Record<string, StanceAnswer> = { a: 'agree', d: 'disagree', n: 'unsure' }
      if (map[k]) {
        const st = L.statements[L.active]
        if (!st || L.posting) return
        if (L.confirmed[st.statement_id] && !L.changing[st.statement_id]) return
        e.preventDefault()
        void submit({ statementId: st.statement_id, answer: map[k]! })
      } else if (k === 'enter' && !(t && (t.tagName === 'BUTTON' || t.tagName === 'A'))) {
        e.preventDefault()
        nextScreen()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [submit, nextScreen])

  // --- render ---------------------------------------------------------------------------------------------------------
  if (packQ.isLoading) {
    return (
      <div className="folio stance-game stance-message" style={HOUSE_STYLE} role="status">
        Loading the challenge…
      </div>
    )
  }
  if (packQ.isError || !pack) {
    return (
      <div className="folio stance-game stance-message" style={HOUSE_STYLE} role="alert">
        <p>This challenge could not be loaded{errorStatus(packQ.error) === 404 ? ': there is no such topic.' : '.'}</p>
        <button type="button" className="folio-btn" onClick={() => void packQ.refetch()}>
          Try again
        </button>
      </div>
    )
  }

  const label = placeLabel(stateName, city)
  const placeQuery = (() => {
    const q = new URLSearchParams()
    if (stateCode) q.set('state', stateCode)
    if (city) q.set('city', city)
    const s = q.toString()
    return s ? `?${s}` : ''
  })()
  const railLabels = [...statements.map((s) => s.category), 'Where you stood']
  const answeredFlags = [...statements.map((s) => Boolean(confirmed[s.statement_id])), false]
  const minSample = resultsQ.data?.min_sample ?? null
  const rounds = statements.map((s) => ({ statementId: s.statement_id, answer: confirmed[s.statement_id] ?? null, results: resultsById.get(s.statement_id) }))

  return (
    <div className="folio stance-game" style={HOUSE_STYLE} ref={gameRef} data-mode={animated ? 'pinned' : 'stacked'}>
      <ScopeBar
        backTo={`/stories${placeQuery}`}
        backLabel="← Data stories"
        title={pack.title}
        label={label}
        stateCode={stateCode}
        stateName={stateName}
        city={city}
        current={active < n ? (statements[active]?.category ?? '') : 'Where you stood'}
        placeOpen={placeOpen}
        onPlaceOpenChange={setPlaceOpen}
        onApply={applyPlace}
      />
      <p className="folio-sr-only" aria-live="polite">
        {active < n ? (statements[active]?.category ?? '') : 'Where you stood'}
      </p>
      <div className="stance-body">
        <Cover packTitle={pack.title} statementCount={n} onStart={() => goToRound(0)} />
        <div className="stance-acts">
          {statements.map((st, i) => (
            <RoundPanel
              key={st.statement_id}
              statement={st}
              index={i}
              total={n}
              active={active === i}
              near={Math.abs(active - i) <= 1}
              scope={{ stateCode, stateName, city }}
              results={resultsById.get(st.statement_id)}
              resultsLoading={resultsQ.isLoading || resultsQ.isFetching}
              resultsFailed={resultsQ.isError}
              minSample={minSample}
              answer={confirmed[st.statement_id] ?? null}
              posting={posting === st.statement_id}
              error={errors[st.statement_id]?.message ?? null}
              changing={Boolean(changing[st.statement_id])}
              onAnswer={(a) => void submit({ statementId: st.statement_id, answer: a })}
              onRetry={() => {
                const at = errors[st.statement_id]?.attempt
                if (at) void submit(at)
              }}
              onChange={() => setChanging((c) => ({ ...c, [st.statement_id]: true }))}
              nextLabel={i < n - 1 ? statements[i + 1]!.category : 'Where you stood'}
              onPrev={i > 0 ? () => goToRound(activeRef.current - 1) : undefined}
              onNext={() => goToRound(activeRef.current + 1)}
            />
          ))}
          <EndPanel
            index={n}
            rounds={rounds}
            stateName={stateName}
            city={city}
            otherPacks={(packsQ.data ?? []).filter((p) => p.pack_id !== packId)}
            placeQuery={placeQuery}
            onJump={goToRound}
            onBack={() => goToRound(n - 1)}
            storyLink={`/stories/data-centers${placeQuery}`}
            onChangePlace={() => {
              setPlaceOpen(true)
            }}
          />
        </div>
        <ProgressRail labels={railLabels} active={active} answered={answeredFlags} onJump={goToRound} navLabel="Challenge screens" />
      </div>
      <p className="stance-keys">Keys: A agree · D disagree · N not sure · PageDown, Space or Enter next · PageUp or Shift+Space back</p>
    </div>
  )
}
