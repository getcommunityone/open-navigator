import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQueries, useQuery } from '@tanstack/react-query'
import {
  fetchRankings,
  fetchRankingTopics,
  type BandFilter,
  type RankingPlace,
  type RankingsResponse,
  type RankingTopicSummary,
} from '../api/rankings'
import StanceGauge from '../components/rankings/StanceGauge'
import PlacePanel from '../components/rankings/PlacePanel'
import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { BANDS, BAND_LABEL, BAND_SHORT, sided, summarize } from '../utils/rankings'
import { useDocumentTitle } from '../utils/useDocumentTitle'

const chip = (on: boolean) =>
  `rounded-full border px-3 py-1.5 text-sm ${on ? 'border-teal-800 bg-teal-800 text-white' : 'border-gray-300 bg-white text-gray-800 hover:bg-gray-50'}`

function parseBand(v: string | null): BandFilter | undefined {
  return v === 'large' || v === 'mid' || v === 'small' ? v : undefined
}

/** One topic: its gauge, the place panel, and (when `detail`) the ranked list grouped by size band. */
function TopicBlock({ data, band, state, detail, headingLevel }: { data: RankingsResponse; band?: BandFilter; state?: string; detail: boolean; headingLevel: 'h2' | 'h3' }) {
  const [sel, setSel] = useState<RankingPlace | null>(null)
  const filtered = Boolean(band || state)
  const grouped = useMemo(() => {
    const out: Record<string, RankingPlace[]> = {}
    for (const p of data.places.filter((x) => x.is_ranked)) (out[p.size_band] ??= []).push(p)
    for (const k of Object.keys(out)) out[k].sort((a, b) => (a.band_rank ?? 1e9) - (b.band_rank ?? 1e9) || b.shrunk_against_share - a.shrunk_against_share)
    return out
  }, [data.places])
  const unranked = data.places.length - data.places.filter((p) => p.is_ranked).length
  return (
    <div data-testid="topic-block">
      <StanceGauge
        topicName={data.topic.name}
        places={data.places}
        medianLabel={filtered ? 'Median of these places' : 'National median'}
        selectedId={sel?.jurisdiction_id}
        onSelect={setSel}
        headingLevel={headingLevel}
      />
      {sel && <PlacePanel place={sel} topicId={data.topic.topic_id} topicName={data.topic.name} onClose={() => setSel(null)} />}
      {!detail && (
        <p className="mt-2 text-sm">
          <Link className="font-medium text-primary-700 hover:underline" to={`/where-towns-stand?${new URLSearchParams({ topic: data.topic.slug, ...(band ? { band } : {}), ...(state ? { state } : {}) })}`}>
            See the ranked list for {data.topic.name}
          </Link>
        </p>
      )}
      {detail && (
        <div className="mt-4">
          {summarize(data.places).ranked === 0 && <p className="text-sm text-gray-700">No place has enough speakers to rank yet. {unranked} {unranked === 1 ? 'place is' : 'places are'} shown as light dots.</p>}
          {(['large', 'mid', 'small', 'unknown'] as const).map((b) =>
            grouped[b]?.length ? (
              <section key={b} className="mb-4" aria-label={`Ranked ${BAND_LABEL[b]}`}>
                <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-600">Ranked {BAND_LABEL[b]}</h3>
                <ol className="m-0 list-none p-0">
                  {grouped[b].slice(0, 25).map((p) => (
                    <li key={String(p.jurisdiction_id)} className="border-t border-gray-200">
                      <button type="button" className="flex w-full items-baseline justify-between gap-3 py-2 text-left text-sm hover:bg-gray-50" onClick={() => setSel(p)}>
                        <span className="font-medium">{p.band_rank != null ? `${p.band_rank}. ` : ''}{p.jurisdiction_name}, {p.state_code}</span>
                        <span className="text-gray-700">{p.speakers_against} of {sided(p)} speakers against</span>
                      </button>
                    </li>
                  ))}
                </ol>
                {grouped[b].length > 25 && <p className="text-xs text-gray-600">Showing the top 25 of {grouped[b].length}. The gauge above has every place.</p>}
              </section>
            ) : null,
          )}
        </div>
      )}
    </div>
  )
}

export default function WhereTownsStand() {
  useDocumentTitle('Where towns stand')
  const [sp, setSp] = useSearchParams()
  const topic = (sp.get('topic') || '').trim() || undefined
  const band = parseBand(sp.get('band'))
  const stateRaw = (sp.get('state') || '').trim().toUpperCase()
  const state = STATE_CODES.includes(stateRaw) ? stateRaw : undefined

  const topicsQ = useQuery<RankingTopicSummary[]>({ queryKey: ['rankings-topics'], queryFn: fetchRankingTopics, staleTime: 5 * 60_000, retry: 1 })
  const topics = useMemo(() => [...(topicsQ.data ?? [])].sort((a, b) => b.places_ranked - a.places_ranked || a.name.localeCompare(b.name)), [topicsQ.data])
  const shown = topic ? [topic] : topics.map((t) => t.slug)
  const results = useQueries({
    queries: shown.map((slug) => ({ queryKey: ['rankings', slug, band ?? '', state ?? ''], queryFn: () => fetchRankings(slug, band, state), staleTime: 5 * 60_000, retry: 1 })),
  })

  const set = (k: string, v: string | undefined) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v)
    else n.delete(k)
    setSp(n, { replace: true })
  }
  const scopeLabel = `${state ? STATE_CODE_TO_NAME[state] ?? state : 'National'} · ${band ? BAND_SHORT[band] + ' places' : 'all sizes'}`
  const failed = topic ? results[0]?.isError : topicsQ.isError
  const loading = topic ? results[0]?.isLoading : topicsQ.isLoading || results.some((r) => r.isLoading)
  const ready = results.filter((r) => r.data).map((r) => r.data as RankingsResponse)
  const key = `${topic ?? 'all'}|${band ?? ''}|${state ?? ''}`

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <p className="m-0 text-sm font-medium text-gray-600">Where towns stand · {scopeLabel}</p>
      <h1 className="mb-2 mt-1 text-2xl font-bold">Where towns stand on contested local questions</h1>
      <p className="mb-4 max-w-2xl text-sm text-gray-700">
        Each dot is a place. It shows how the public speakers at that place's meetings leaned on a question, from "All against" on the left to "All for" on the right.
      </p>

      <div className="mb-4 flex flex-col gap-2" aria-label="Scope controls">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Place size">
          <button type="button" className={chip(!band)} aria-pressed={!band} onClick={() => set('band', undefined)}>All sizes</button>
          {BANDS.map((b) => (
            <button key={b} type="button" className={chip(band === b)} aria-pressed={band === b} onClick={() => set('band', b)}>{BAND_SHORT[b][0].toUpperCase() + BAND_SHORT[b].slice(1)}</button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-gray-700" htmlFor="wts-state">State</label>
          <select id="wts-state" className="rounded border border-gray-300 px-2 py-1.5 text-sm" value={state ?? ''} onChange={(e) => set('state', e.target.value || undefined)}>
            <option value="">All states</option>
            {STATE_CODES.map((c) => <option key={c} value={c}>{STATE_CODE_TO_NAME[c] ?? c}</option>)}
          </select>
          <label className="ml-2 text-sm text-gray-700" htmlFor="wts-topic">Topic</label>
          <select id="wts-topic" className="min-w-0 max-w-full rounded border border-gray-300 px-2 py-1.5 text-sm" value={topic ?? ''} onChange={(e) => set('topic', e.target.value || undefined)}>
            <option value="">All topics</option>
            {topics.map((t) => <option key={t.slug} value={t.slug}>{t.name}</option>)}
          </select>
          {(state || band) && (
            <button type="button" className="text-sm font-medium text-primary-700 hover:underline" onClick={() => { if (state) set('state', undefined); else set('band', undefined) }}>
              {state ? 'Broaden to the whole country' : 'Broaden to all sizes'}
            </button>
          )}
        </div>
      </div>

      {loading && <p role="status" className="text-sm text-gray-700">Loading rankings…</p>}
      {failed && <p className="text-sm text-gray-700">No rankings available yet. They could not be loaded right now.</p>}
      {!loading && !failed && ((!topic && topics.length === 0) || (topic && ready.length === 0)) && <p className="text-sm text-gray-700">No rankings available yet.</p>}

      {/* A short fade when the scope or topic changes (CSS only; the #1404 box flight was not reused). */}
      <div key={key} className="wts-fade flex flex-col gap-8" style={{ animation: 'wts-fade 250ms ease-out' }}>
        <style>{`@keyframes wts-fade{from{opacity:0}to{opacity:1}}@media (prefers-reduced-motion: reduce){.wts-fade{animation:none!important}}`}</style>
        {ready.map((d) => (
          <TopicBlock key={d.topic.slug} data={d} band={band} state={state} detail={Boolean(topic)} headingLevel={topic ? 'h2' : 'h3'} />
        ))}
      </div>

      <section className="mt-10 max-w-2xl border-t border-gray-200 pt-6" aria-labelledby="wts-how">
        <h2 id="wts-how" className="text-lg font-semibold">How these rankings work</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-gray-800">
          <li>They are built from what members of the public said at public meetings we have recordings of. A classifier reads each comment, and we check it against hand labels.</li>
          <li>This is not a poll or a survey, and it does not represent all residents. It shows who spoke up.</li>
          <li>Each speaker counts once per place and topic, on their usual side. Mixed or unclear comments are not counted.</li>
          <li>A place is ranked only with at least 10 speakers who took a side, across at least 2 meetings in the last 24 months. Other places appear as light dots.</li>
          <li>When evidence is thin, a score is pulled toward the national rate, as if 10 extra speakers had split the way the country does.</li>
          <li>Places are ranked against places of a similar size: large, mid-size and small.</li>
          <li>Only places whose meetings we hold appear. A missing place means we have no recordings of it, not that it has no view.</li>
          <li>Officials are kept separate from residents, and shown only when matched to a roster. No resident is named on this page.</li>
        </ul>
      </section>
    </div>
  )
}
