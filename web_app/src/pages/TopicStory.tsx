import { useMemo } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { companySearchTerm } from '../utils/companySearchTerm'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { fetchTopicMeetings, fetchTopicStates } from '../api/topics'
import { highlightSnippet } from '../lib/highlight'
import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import StoryStatesMap, { type StateQuote } from '../components/home/StoryStatesMap'

/**
 * A topic story (#1013): one curated topic's meetings, told from the transcript record. Everything shown is counted or
 * quoted from `topic_transcript_link` (meetings with a verbatim passage) and the decisions search for the topic. The
 * headline states only those counts; there is no sentiment claim without a positions record.
 */
interface TopicStoryDef {
  slug: string
  topicId: number
  title: string
  /** "Short-term rentals came up in …": the noun phrase the headline leads with. */
  subject: string
  lede: string
  /** The API listing the platform companies this story names (#1015), when it has one. */
  companiesPath?: string
}

const TOPIC_STORIES: Record<string, TopicStoryDef> = {
  'short-term-rentals': {
    slug: 'short-term-rentals',
    topicId: 100003,
    title: 'Short-term rentals',
    subject: 'Short-term rentals',
    lede: 'Airbnb, VRBO and vacation rentals: where local governments are talking about them, in the words said at the meeting.',
    companiesPath: '/short-term-rentals/companies',
  },
}

const fmt = (n: number) => n.toLocaleString('en-US')
const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

interface PlatformCompany {
  master_org_id: string
  company_name: string
  aliases: string[]
  website_url: string | null
  meetings: number
  decisions: number
  newest: { title: string | null; date: string | null; jurisdiction_name: string | null; state_code: string | null; url: string | null; evidence: string | null } | null
}

interface DecisionResult {
  title: string
  subtitle?: string
  description?: string
  url?: string
}

const PAGE = 8

export default function TopicStory({ slug: slugProp }: { slug?: string }) {
  const params = useParams<{ storyId?: string }>()
  const def = TOPIC_STORIES[slugProp ?? params.storyId ?? '']
  const [sp, setSp] = useSearchParams()
  const raw = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(raw) ? raw : null
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const label = stateName ?? 'National'

  const setState = (code: string | null) =>
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev)
        if (code) n.set('state', code)
        else n.delete('state')
        n.delete('city')
        return n
      },
      { replace: false },
    )

  // The map always shows the whole country (each state its own count); the headline and lists follow the scope.
  const national = useQuery({
    queryKey: ['topic-story', def?.topicId, 'states'],
    queryFn: () => fetchTopicStates(def!.topicId),
    enabled: Boolean(def),
    staleTime: 5 * 60_000,
  })
  const scoped = useMemo(() => {
    const all = national.data
    if (!all) return null
    if (!stateCode) return { meetings: all.total_meetings, states: all.states.length }
    const s = all.states.find((x) => x.state_code === stateCode)
    return { meetings: s?.meetings ?? 0, states: s ? 1 : 0 }
  }, [national.data, stateCode])

  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote>()
    for (const m of national.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      out.set(m.state_code, {
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        url: m.video_url ?? null,
      })
    }
    return out
  }, [national.data])

  const meetings = useInfiniteQuery({
    queryKey: ['topic-story', def?.topicId, 'meetings', stateCode ?? ''],
    queryFn: ({ pageParam }) => fetchTopicMeetings(def!.topicId, { state: stateCode ?? undefined, limit: PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const seen = pages.reduce((a, p) => a + p.items.length, 0)
      return seen < last.total ? seen : undefined
    },
    enabled: Boolean(def),
  })

  const decisions = useQuery({
    queryKey: ['topic-story', def?.topicId, 'decisions', stateCode ?? ''],
    queryFn: async () => {
      const res = await api.get('/search', {
        params: { types: 'decisions', topic_id: def!.topicId, limit: 6, sort: 'date_desc', ...(stateCode ? { state: stateCode } : {}) },
      })
      return {
        total: (res.data?.type_totals?.decisions as number | undefined) ?? 0,
        items: (res.data?.results?.decisions ?? []) as DecisionResult[],
      }
    },
    enabled: Boolean(def),
  })

  // The platform companies named in this scope's meetings and decisions (#1015).
  const companies = useQuery({
    queryKey: ['topic-story', def?.topicId, 'companies', stateCode ?? ''],
    queryFn: async () =>
      ((await api.get(def!.companiesPath!, { params: stateCode ? { state: stateCode } : {} })).data?.companies ?? []) as PlatformCompany[],
    enabled: Boolean(def?.companiesPath),
    staleTime: 5 * 60_000,
  })

  if (!def) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16">
        <p className="text-stone-700">That story isn't available.</p>
        <Link to="/stories" className="text-teal-700 underline">
          See all data stories
        </Link>
      </main>
    )
  }

  const headline =
    scoped == null
      ? def.title
      : scoped.meetings === 0
        ? `No meetings on record about ${def.subject.toLowerCase()} ${stateName ? `in ${stateName}` : 'yet'}.`
        : stateName
          ? `${def.subject} came up in ${fmt(scoped.meetings)} ${scoped.meetings === 1 ? 'meeting' : 'meetings'} in ${stateName}.`
          : `${def.subject} came up in ${fmt(scoped.meetings)} meetings across ${fmt(scoped.states)} states.`
  const items = meetings.data?.pages.flatMap((p) => p.items) ?? []
  const total = meetings.data?.pages[0]?.total ?? 0

  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6">
      <div className="flex items-start justify-between gap-4">
        <p className="font-mono text-xs uppercase tracking-widest text-teal-700">Data story · {def.title}</p>
        {/* Close (#1017): back to the home page's stories, keeping the place. */}
        <Link
          to={`/${stateCode ? `?state=${stateCode}` : ''}#data-stories`}
          aria-label="Close story"
          title="Close"
          className="-mt-2 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-stone-300 bg-white text-2xl leading-none text-stone-800 hover:bg-stone-50"
        >
          <span aria-hidden="true">×</span>
        </Link>
      </div>
      <h1 className="mt-2 font-serif text-3xl font-bold leading-tight text-stone-900 sm:text-5xl" aria-busy={national.isPending || undefined}>
        {national.isError ? def.title : headline}
      </h1>
      <p className="mt-3 max-w-2xl text-stone-600">{def.lede}</p>
      <p className="mt-2 text-sm text-stone-500">Counted from local meeting recordings and transcripts that mention the topic.</p>

      {/* Scope label = the applied filter (CLAUDE.md), with a one-click broaden and a picker. */}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-stone-600">Showing:</span>
        <strong className="text-stone-900">{label}</strong>
        {stateCode && (
          <button type="button" onClick={() => setState(null)} className="text-teal-700 underline underline-offset-2">
            National
          </button>
        )}
        <select
          aria-label="Choose a state"
          value={stateCode ?? ''}
          onChange={(e) => setState(e.target.value || null)}
          className="rounded-md border border-stone-300 bg-white px-2 py-1 text-stone-900"
        >
          <option value="">All states</option>
          {[...STATE_CODES]
            .sort((a, b) => (STATE_CODE_TO_NAME[a] ?? a).localeCompare(STATE_CODE_TO_NAME[b] ?? b))
            .map((c) => (
              <option key={c} value={c}>
                {STATE_CODE_TO_NAME[c] ?? c}
              </option>
            ))}
        </select>
      </div>

      <section className="mx-auto mt-6 max-w-4xl" aria-label={`Map of meetings about ${def.title.toLowerCase()} by state`}>
        {national.isError ? (
          <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
        ) : (
          <StoryStatesMap
            byState={national.data?.states}
            quotes={quotes}
            highlight={stateCode}
            href={(code) => `/stories/${def.slug}?state=${encodeURIComponent(code)}`}
            subject={def.subject.toLowerCase()}
          />
        )}
      </section>

      {def.companiesPath && (
        <section className="mt-10" aria-labelledby="topic-companies-h">
          <h2 id="topic-companies-h" className="font-serif text-2xl font-semibold text-stone-900">
            Companies named
          </h2>
          <p className="mt-1 text-sm text-stone-500">
            The rental platforms named in {label === 'National' ? 'these' : `${label}'s`} meetings and decisions, counted from the record.
          </p>
          {companies.isError ? (
            <p className="mt-4 text-sm text-stone-500">Companies could not be loaded right now.</p>
          ) : companies.isPending ? (
            <p className="mt-4 text-sm text-stone-500">Loading companies…</p>
          ) : (
            <ul className="mt-4 grid gap-4 sm:grid-cols-3">
              {companies.data!.map((c) => {
                const brands = c.aliases.filter((a) => a !== c.company_name && !a.includes(','))
                return (
                  <li key={c.master_org_id} className="rounded-xl border border-stone-200 bg-white p-4">
                    <p className="text-base font-semibold text-stone-900">
                      <Link to={`/organizations/${encodeURIComponent(c.master_org_id)}`} className="hover:text-teal-700">
                        {c.company_name}
                      </Link>
                    </p>
                    {brands.length > 0 && <p className="text-xs text-stone-500">{brands.join(', ')}</p>}
                    {c.meetings + c.decisions === 0 ? (
                      <p className="mt-2 text-sm text-stone-500">Not named in {label === 'National' ? 'any meeting on record' : `${label}'s meetings on record`}.</p>
                    ) : (
                      <p className="mt-2 text-sm text-stone-700">
                        <Link to={`/search?q=${encodeURIComponent(companySearchTerm(c.company_name, c.newest?.evidence))}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`} className="font-semibold text-teal-700">
                          {fmt(c.meetings)} {c.meetings === 1 ? 'meeting' : 'meetings'}
                        </Link>
                        {' · '}
                        {fmt(c.decisions)} {c.decisions === 1 ? 'decision' : 'decisions'}
                      </p>
                    )}
                    {c.newest?.evidence && (
                      <blockquote className="mt-2 border-l-2 border-teal-600 pl-3 text-sm italic leading-relaxed text-stone-700">
                        “{highlightSnippet(c.newest.evidence)}”
                        <footer className="mt-1 not-italic text-xs text-stone-500">
                          {[c.newest.jurisdiction_name, c.newest.state_code].filter(Boolean).join(', ')}
                          {fmtDate(c.newest.date) ? ` · ${fmtDate(c.newest.date)}` : ''}
                          {c.newest.url && (
                            <>
                              {' · '}
                              {c.newest.url.startsWith('/') ? (
                                <Link to={c.newest.url} className="text-teal-700">Open</Link>
                              ) : (
                                <a href={c.newest.url} target="_blank" rel="noopener noreferrer" className="text-teal-700">Watch ↗</a>
                              )}
                            </>
                          )}
                        </footer>
                      </blockquote>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      )}

      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="topic-meetings-h">
          <h2 id="topic-meetings-h" className="font-serif text-2xl font-semibold text-stone-900">
            What was said{total ? ` · ${fmt(total)} ${total === 1 ? 'meeting' : 'meetings'}` : ''}
          </h2>
          <p className="mt-1 text-sm text-stone-500">Newest first. Each passage is quoted from the meeting transcript.</p>
          {meetings.isError ? (
            <p className="mt-4 text-sm text-stone-500">Meetings could not be loaded right now.</p>
          ) : meetings.isPending ? (
            <p className="mt-4 text-sm text-stone-500">Loading meetings…</p>
          ) : items.length === 0 ? (
            <p className="mt-4 text-sm text-stone-500">No meetings on record for {label}.</p>
          ) : (
            <ul className="mt-4 space-y-4">
              {items.map((m) => (
                <li key={m.video_id} className="rounded-xl border border-stone-200 bg-white p-4">
                  <p className="text-sm font-semibold text-stone-900">{m.title ?? 'Meeting'}</p>
                  <p className="text-xs text-stone-500">
                    {[m.jurisdiction_name ?? m.city, m.state].filter(Boolean).join(', ')}
                    {fmtDate(m.date) ? ` · ${fmtDate(m.date)}` : ''}
                  </p>
                  {m.excerpt && (
                    <blockquote className="mt-2 border-l-2 border-teal-600 pl-3 text-[15px] italic leading-relaxed text-stone-700">
                      “{highlightSnippet(m.excerpt)}”
                    </blockquote>
                  )}
                  {m.video_url && (
                    <a href={m.video_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm font-semibold text-teal-700">
                      Watch the meeting ↗
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
          {meetings.hasNextPage && (
            <button
              type="button"
              onClick={() => meetings.fetchNextPage()}
              disabled={meetings.isFetchingNextPage}
              className="mt-4 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 hover:bg-stone-50 disabled:opacity-50"
            >
              {meetings.isFetchingNextPage ? 'Loading…' : 'Show more meetings'}
            </button>
          )}
        </section>

        <section aria-labelledby="topic-decisions-h">
          <h2 id="topic-decisions-h" className="font-serif text-2xl font-semibold text-stone-900">
            What was decided{decisions.data?.total ? ` · ${fmt(decisions.data.total)}` : ''}
          </h2>
          <p className="mt-1 text-sm text-stone-500">Decisions whose record mentions the topic, newest first.</p>
          {decisions.isError ? (
            <p className="mt-4 text-sm text-stone-500">Decisions could not be loaded right now.</p>
          ) : decisions.isPending ? (
            <p className="mt-4 text-sm text-stone-500">Loading decisions…</p>
          ) : (decisions.data?.items.length ?? 0) === 0 ? (
            <p className="mt-4 text-sm text-stone-500">No decisions on record for {label}.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {decisions.data!.items.map((d, i) => (
                <li key={d.url ?? i} className="rounded-xl border border-stone-200 bg-white p-4">
                  {d.url ? (
                    <Link to={d.url} className="text-sm font-semibold text-stone-900 hover:text-teal-700">
                      {d.title}
                    </Link>
                  ) : (
                    <p className="text-sm font-semibold text-stone-900">{d.title}</p>
                  )}
                  {d.subtitle && <p className="mt-0.5 text-xs text-stone-500">{d.subtitle}</p>}
                  {d.description && <p className="mt-2 text-sm leading-relaxed text-stone-700">{highlightSnippet(d.description)}</p>}
                </li>
              ))}
            </ul>
          )}
          {(decisions.data?.total ?? 0) > (decisions.data?.items.length ?? 0) && (
            <Link
              to={`/search?types=decisions&topic_id=${def.topicId}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}`}
              className="mt-4 inline-block text-sm font-semibold text-teal-700"
            >
              See all {fmt(decisions.data!.total)} decisions →
            </Link>
          )}
        </section>
      </div>
    </main>
  )
}
